// Offline ETL reader: raw QPC, selected scheduler events and TDH-decoded GPU metadata.
// Build with the installed Windows SDK; never starts/stops an ETW session.
#include <windows.h>
#include <evntrace.h>
#include <evntcons.h>
#include <tdh.h>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <string>
#include <vector>
#include <map>
#include <stdexcept>
#include <algorithm>
#pragma comment(lib, "advapi32.lib")
#pragma comment(lib, "tdh.lib")

static FILE* records;
static FILE* schemas;
static ULONGLONG frequency;
static double loMs, hiMs;
static unsigned long long eventCount, keptCount, propertyErrors;
static double firstMs;
static std::string failure;
struct Schema {
    std::vector<BYTE> buffer;
    std::wstring task, opcode, provider;
    unsigned long long count = 0;
    int number = 0;
};
static std::map<std::string, Schema> cache;
static std::map<unsigned, unsigned long long> perfCounts;
static const GUID threadGuid = {0x3d6fa8d1,0xfe05,0x11d0,{0x9d,0xda,0,0xc0,0x4f,0xd7,0xba,0x7c}};
static const GUID perfGuid = {0xce1dbfb4,0x137e,0x4da6,{0x87,0xb0,0x3f,0x59,0xaa,0x10,0x2c,0xbc}};
static const GUID imageGuid = {0x2cb15d1d,0x5fc1,0x11d2,{0xab,0xe1,0,0xa0,0xc9,0x11,0xf5,0x18}};
static const GUID dxgGuid = {0x802ec45a,0x1e99,0x4b83,{0x99,0x20,0x87,0xc9,0x82,0x77,0xba,0x9d}};
static const GUID dxgiGuid = {0xca11c036,0x0102,0x4a2d,{0xa6,0xad,0xf0,0x3c,0xfe,0xd5,0xd3,0xc9}};
static std::wstring text(TRACE_EVENT_INFO* info, ULONG offset) {
    return offset ? reinterpret_cast<WCHAR*>(reinterpret_cast<BYTE*>(info) + offset) : L"";
}
static void hex(FILE* file, const BYTE* data, size_t size) {
    static const char digits[] = "0123456789abcdef";
    std::string s(size * 2, '0');
    for (size_t i=0; i<size; ++i) { s[2*i]=digits[data[i]>>4]; s[2*i+1]=digits[data[i]&15]; }
    fwrite(s.data(), 1, s.size(), file);
}
static Schema& schema(EVENT_RECORD* event) {
    std::string key(reinterpret_cast<char*>(&event->EventHeader.ProviderId), sizeof(GUID));
    key.append(reinterpret_cast<char*>(&event->EventHeader.EventDescriptor), sizeof(EVENT_DESCRIPTOR));
    auto [it, inserted] = cache.try_emplace(key);
    auto& s = it->second;
    if (inserted) {
        s.number = static_cast<int>(cache.size());
        ULONG size = 0;
        auto status = TdhGetEventInformation(event, 0, nullptr, nullptr, &size);
        if (status == ERROR_INSUFFICIENT_BUFFER) {
            s.buffer.resize(size);
            auto info = reinterpret_cast<TRACE_EVENT_INFO*>(s.buffer.data());
            status = TdhGetEventInformation(event, 0, nullptr, info, &size);
            if (status == ERROR_SUCCESS) {
                s.task=text(info, info->TaskNameOffset); s.opcode=text(info, info->OpcodeNameOffset);
                s.provider=text(info, info->ProviderNameOffset);
                fprintf(schemas, "%d\t%ls\t%ls\t%ls\t%u\t%u\t%u", s.number, s.provider.c_str(), s.task.c_str(), s.opcode.c_str(), event->EventHeader.EventDescriptor.Id, event->EventHeader.EventDescriptor.Version, event->EventHeader.EventDescriptor.Opcode);
                for (ULONG i=0; i<info->TopLevelPropertyCount; ++i) {
                    auto& p=info->EventPropertyInfoArray[i];
                    fprintf(schemas, "\t%ls:%u:%u:%u:%u", text(info,p.NameOffset).c_str(), p.Flags, p.nonStructType.InType, p.count, p.length);
                }
                fputc('\n',schemas);
            } else s.buffer.clear();
        }
        if (s.buffer.empty()) fprintf(schemas, "%d\tUNDECODABLE\t%lu\t\t%u\t%u\t%u\tbytes=%u\n",s.number,status,event->EventHeader.EventDescriptor.Id,event->EventHeader.EventDescriptor.Version,event->EventHeader.EventDescriptor.Opcode,event->UserDataLength);
    }
    ++s.count;
    return s;
}
static bool named(const std::wstring& value, const wchar_t* name) {
    return value == name;
}
static void consume(EVENT_RECORD* event) {
    ++eventCount;
    auto& hdr=event->EventHeader;
    const bool thread=IsEqualGUID(hdr.ProviderId,threadGuid);
    const bool perf=IsEqualGUID(hdr.ProviderId,perfGuid);
    if (perf) ++perfCounts[hdr.EventDescriptor.Opcode];
    const bool sample=perf && hdr.EventDescriptor.Opcode==46;
    const bool image=IsEqualGUID(hdr.ProviderId,imageGuid);
    const bool dxg=IsEqualGUID(hdr.ProviderId,dxgGuid);
    const bool dxgi=IsEqualGUID(hdr.ProviderId,dxgiGuid);
    const double ms=static_cast<double>(hdr.TimeStamp.QuadPart)*1000.0/frequency;
    if (eventCount==1) { firstMs=ms; printf("first_qpc=%lld first_ms=%.7f\n",hdr.TimeStamp.QuadPart,ms); fflush(stdout); }
    if (!(thread || sample || image || dxg || dxgi)) return;
    auto& s=schema(event);
    const bool inWindow=ms>=loMs && ms<hiMs;
    const bool cpuWindow=inWindow || ms<firstMs+200.0;
    bool raw=false, keep=false;
    const char* kind="fields";
    if (thread && (hdr.EventDescriptor.Opcode==36 || hdr.EventDescriptor.Opcode==50)) {
        raw=true; keep=cpuWindow; kind=hdr.EventDescriptor.Opcode==36 ? "cswitch" : "ready";
    } else if (sample) { raw=true; keep=cpuWindow; kind="sample"; }
    else if (image || thread) keep=true;
    else if (dxgi) keep=named(s.task,L"Present") && (inWindow || ms<loMs);
    else if (dxg) {
        const bool metadata=named(s.task,L"Device") || named(s.task,L"Context") || named(s.task,L"HwQueue") || named(s.task,L"NodeMetadata");
        const bool runtime=named(s.task,L"QueuePacket") || named(s.task,L"DmaPacket") || s.task.find(L"SynchronizationObject")!=std::wstring::npos || named(s.task,L"UnwaitQueuePacket") || named(s.task,L"VSyncDPC");
        keep=metadata || (runtime && inWindow) || (named(s.task,L"VSyncDPC") && ms<loMs);
    }
    if (!keep) return;
    ++keptCount;
    fprintf(records,"%lld\t%lu\t%lu\t%u\t%d\t%s\t%u",hdr.TimeStamp.QuadPart,hdr.ProcessId,hdr.ThreadId,event->BufferContext.ProcessorIndex,s.number,kind,hdr.Flags);
    if (raw) { fputc('\t',records); hex(records,static_cast<BYTE*>(event->UserData),event->UserDataLength); }
    else if (!s.buffer.empty()) {
        auto info=reinterpret_cast<TRACE_EVENT_INFO*>(s.buffer.data());
        for (ULONG i=0; i<info->TopLevelPropertyCount; ++i) {
            auto& prop=info->EventPropertyInfoArray[i];
            auto name=text(info,prop.NameOffset);
            PROPERTY_DATA_DESCRIPTOR desc{}; desc.PropertyName=reinterpret_cast<ULONGLONG>(name.c_str()); desc.ArrayIndex=ULONG_MAX;
            ULONG size=0;
            auto status=TdhGetPropertySize(event,0,nullptr,1,&desc,&size);
            if (status!=ERROR_SUCCESS || size>65536) { ++propertyErrors; continue; }
            std::vector<BYTE> data(size);
            status=TdhGetProperty(event,0,nullptr,1,&desc,size,data.data());
            if (status!=ERROR_SUCCESS) { ++propertyErrors; continue; }
            fprintf(records,"\t%ls=",name.c_str()); hex(records,data.data(),data.size());
        }
    }
    fputc('\n',records);
}
static void WINAPI callback(EVENT_RECORD* event) {
    // C++ exceptions must never cross the Windows callback ABI.
    if (!failure.empty()) return;
    try { consume(event); } catch(const std::exception& e) { failure=e.what(); }
}
int wmain(int argc, wchar_t** argv) {
    if (argc==2 && wcscmp(argv[1],L"--selfcheck")==0) {
        if (sizeof(EVENT_DESCRIPTOR)!=16 || offsetof(EVENT_RECORD,UserDataLength)!=86 || sizeof(void*)!=8) return 1;
        puts("ETL reader x64 ABI selfcheck PASS"); return 0;
    }
    if (argc!=5) { fputs("etl_extract <input.etl> <output-prefix> <qpc-lo-ms> <qpc-hi-ms>\n",stderr); return 2; }
    loMs=wcstod(argv[3],nullptr); hiMs=wcstod(argv[4],nullptr);
    if (!(hiMs>loMs && loMs>=0)) return 2;
    std::wstring prefix=argv[2];
    if (_wfopen_s(&records,(prefix+L".tsv").c_str(),L"wbx") || _wfopen_s(&schemas,(prefix+L".schemas.tsv").c_str(),L"wbx")) { fputs("Cannot create new output files\n",stderr); return 3; }
    setvbuf(records,nullptr,_IOFBF,1<<20);
    EVENT_TRACE_LOGFILEW log{};
    log.LogFileName=argv[1];
    log.ProcessTraceMode=PROCESS_TRACE_MODE_EVENT_RECORD | PROCESS_TRACE_MODE_RAW_TIMESTAMP;
    log.EventRecordCallback=callback;
    TRACEHANDLE handle=OpenTraceW(&log);
    if (handle==INVALID_PROCESSTRACE_HANDLE) { fprintf(stderr,"OpenTrace error %lu\n",GetLastError()); return 4; }
    frequency=log.LogfileHeader.PerfFreq.QuadPart;
    if (!frequency || log.LogfileHeader.ReservedFlags!=1) { fputs("Trace clock is not QPC\n",stderr); CloseTrace(handle); return 5; }
    printf("frequency=%llu start_filetime=%lld boot_filetime=%lld pointer_size=%lu clock=%lu\n",frequency,log.LogfileHeader.StartTime.QuadPart,log.LogfileHeader.BootTime.QuadPart,log.LogfileHeader.PointerSize,log.LogfileHeader.ReservedFlags);
    fflush(stdout);
    ULONG status=ProcessTrace(&handle,1,nullptr,nullptr);
    CloseTrace(handle);
    bool ioerror=ferror(records)!=0 || ferror(schemas)!=0;
    if (fclose(records)!=0) ioerror=true;
    if (fclose(schemas)!=0) ioerror=true;
    printf("status=%lu events=%llu kept=%llu property_errors=%llu ioerror=%d failure=%s\n",status,eventCount,keptCount,propertyErrors,ioerror,failure.c_str());
    FILE* counts=nullptr;
    if (_wfopen_s(&counts,(prefix+L".counts.tsv").c_str(),L"wbx")) return 6;
    for (auto& [key,s]:cache) fprintf(counts,"%d\t%llu\t%ls\t%ls\t%ls\n",s.number,s.count,s.provider.c_str(),s.task.c_str(),s.opcode.c_str());
    fclose(counts);
    for (auto& [opcode,count]:perfCounts) printf("perf_opcode=%u count=%llu\n",opcode,count);
    return status==ERROR_SUCCESS && !ioerror && failure.empty() && keptCount ? 0 : 7;
}
