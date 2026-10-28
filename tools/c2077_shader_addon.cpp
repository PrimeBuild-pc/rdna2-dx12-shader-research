// Exact-bytecode DX12 override for one Cyberpunk shader; no on-disk cache patches.
#define WIN32_LEAN_AND_MEAN
#define NOMINMAX
#include <reshade.hpp>
#include <bcrypt.h>
#include <atomic>
#include <cassert>
#include <cstdio>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <map>
#include <mutex>
#include <string>
#include <vector>
#include "shader_payloads.hpp"
#pragma comment(lib,"bcrypt.lib")
using namespace reshade::api;
namespace fs=std::filesystem;

enum class Mode { observe,control,canary };
static Mode mode=Mode::control;
static std::atomic<bool> enabled=false;
static std::atomic<unsigned long long> pipeline_inits=0,matches=0,cloned=0,failed=0,bound=0,presents=0;
static std::atomic<ULONGLONG> last_log=0;
static std::mutex pipeline_mutex,log_mutex;
using Key=std::pair<uintptr_t,uint64_t>;
static std::map<Key,pipeline> overrides;
static HANDLE log_file=INVALID_HANDLE_VALUE;
static thread_local bool internal_call=false;
struct InternalCall { InternalCall(){internal_call=true;} ~InternalCall(){internal_call=false;} };

static const char* mode_name() { return mode==Mode::canary?"canary":mode==Mode::control?"control":"observe"; }
static bool parse_mode(std::string value,Mode& result) {
    while(!value.empty() && (value.back()=='\r'||value.back()=='\n'||value.back()==' '||value.back()=='\t'))value.pop_back();
    if(value=="control")result=Mode::control;
    else if(value=="canary")result=Mode::canary;
    else if(value=="observe")result=Mode::observe;
    else return false;
    return true;
}
static void snapshot(const char* event) noexcept {
    try {
        char line[768];
        int n=snprintf(line,sizeof(line),
            "{\"schema\":1,\"experiment\":\"C2077-SHADER-LOADER-001\",\"pid\":%lu,\"event\":\"%s\",\"mode\":\"%s\","
            "\"dx12_pipeline_inits\":%llu,\"matched_original\":%llu,\"cloned_pipelines\":%llu,"
            "\"clone_failures\":%llu,\"bound_calls\":%llu,\"presents\":%llu}\n",
            GetCurrentProcessId(),event,mode_name(),pipeline_inits.load(),matches.load(),cloned.load(),failed.load(),bound.load(),presents.load());
        if(n<=0||static_cast<size_t>(n)>=sizeof(line))return;
        std::lock_guard<std::mutex> lock(log_mutex);
        if(log_file!=INVALID_HANDLE_VALUE){DWORD written=0;WriteFile(log_file,line,n,&written,nullptr);FlushFileBuffers(log_file);}
    } catch(...) { }
}
static bool source_matches(const shader_desc& desc) {
    return desc.code && desc.code_size==sizeof(kOriginal) && memcmp(desc.code,kOriginal,sizeof(kOriginal))==0;
}
static bool prepare_override(uint32_t count,const pipeline_subobject* objects,
                             std::vector<pipeline_subobject>& copy,shader_desc& pixel) {
    if(mode==Mode::observe || !objects || count==0 || count>256)return false;
    uint32_t target=count,pixels=0;
    for(uint32_t i=0;i<count;++i) {
        if(objects[i].type!=pipeline_subobject_type::pixel_shader)continue;
        if(++pixels!=1 || objects[i].count!=1 || !objects[i].data)return false;
        if(source_matches(*static_cast<const shader_desc*>(objects[i].data)))target=i;
    }
    if(target==count)return false;
    copy.assign(objects,objects+count);
    pixel=*static_cast<const shader_desc*>(objects[target].data);
    pixel.code=mode==Mode::control?kControl:kCanary;
    pixel.code_size=mode==Mode::control?sizeof(kControl):sizeof(kCanary);
    copy[target].data=&pixel;
    return true;
}
static void on_init(device* device,pipeline_layout layout,uint32_t count,const pipeline_subobject* objects,pipeline original) noexcept {
    if(!enabled || internal_call || device->get_api()!=device_api::d3d12 || !original.handle || !objects || count==0 || count>256)return;
    try {
        ++pipeline_inits;
        bool found=false;
        for(uint32_t i=0;i<count;++i)
            if(objects[i].type==pipeline_subobject_type::pixel_shader && objects[i].count==1 && objects[i].data && source_matches(*static_cast<const shader_desc*>(objects[i].data)))found=true;
        if(!found)return;
        Key key{reinterpret_cast<uintptr_t>(device),original.handle};
        {std::lock_guard<std::mutex> lock(pipeline_mutex);if(overrides.count(key))return;}
        ++matches;
        pipeline replacement={0};
        if(mode!=Mode::observe) {
            std::vector<pipeline_subobject> copy;shader_desc pixel;
            if(!prepare_override(count,objects,copy,pixel)){++failed;snapshot("unsupported_description");return;}
            InternalCall guard;
            if(!device->create_pipeline(layout,count,copy.data(),&replacement) || !replacement.handle){++failed;snapshot("clone_failed");return;}
        }
        bool inserted;
        {std::lock_guard<std::mutex> lock(pipeline_mutex);inserted=overrides.emplace(key,replacement).second;}
        if(!inserted && replacement.handle){InternalCall guard;device->destroy_pipeline(replacement);}
        if(inserted && replacement.handle)++cloned;
        snapshot(mode==Mode::observe?"original_observed":"clone_ready");
    }catch(...){++failed;enabled=false;snapshot("disabled_after_exception");}
}
static void on_bind(command_list* list,pipeline_stage stages,pipeline original) noexcept {
    if(!enabled || internal_call || !list || (static_cast<uint32_t>(stages)&static_cast<uint32_t>(pipeline_stage::pixel_shader))==0)return;
    try {
        {
            // Keep the clone alive until the bind returns, against concurrent original destruction.
            std::lock_guard<std::mutex> lock(pipeline_mutex);
            auto it=overrides.find({reinterpret_cast<uintptr_t>(list->get_device()),original.handle});
            if(it==overrides.end())return;
            // 'all' avoids the SDK's all_graphics path changing dynamic blend/topology state.
            if(it->second.handle){InternalCall guard;list->bind_pipeline(pipeline_stage::all,it->second);}
        }
        if(++bound==1)snapshot("first_target_bind");
    }catch(...){enabled=false;snapshot("disabled_after_exception");}
}
static void on_destroy(device* device,pipeline original) noexcept {
    if(internal_call)return;
    try {
        pipeline replacement={0};
        {std::lock_guard<std::mutex> lock(pipeline_mutex);auto it=overrides.find({reinterpret_cast<uintptr_t>(device),original.handle});if(it==overrides.end())return;replacement=it->second;overrides.erase(it);}
        if(replacement.handle){InternalCall guard;device->destroy_pipeline(replacement);}
    }catch(...){enabled=false;}
}
static void on_present(command_queue*,swapchain*,const rect*,const rect*,uint32_t,const rect*) noexcept {
    if(!enabled)return;
    ++presents;
    ULONGLONG now=GetTickCount64(),previous=last_log.load();
    if(now-previous>=5000 && last_log.compare_exchange_strong(previous,now))snapshot("heartbeat");
}
static bool host_allowed() {
    wchar_t path[MAX_PATH];DWORD length=GetModuleFileNameW(nullptr,path,MAX_PATH);
    if(!length || length>=MAX_PATH || CompareStringOrdinal(path,-1,kExpectedGamePath,-1,TRUE)!=CSTR_EQUAL)return false;
    std::ifstream stream(fs::path(path),std::ios::binary|std::ios::ate);
    if(!stream)return false;
    auto size=stream.tellg();if(size<=0 || size>128*1024*1024)return false;
    std::vector<unsigned char> bytes(static_cast<size_t>(size));stream.seekg(0);stream.read(reinterpret_cast<char*>(bytes.data()),bytes.size());if(!stream)return false;
    unsigned char digest[32];
    return BCryptHash(BCRYPT_SHA256_ALG_HANDLE,nullptr,0,bytes.data(),static_cast<ULONG>(bytes.size()),digest,sizeof(digest))>=0 && memcmp(digest,kExpectedGameSha,sizeof(digest))==0;
}
extern "C" __declspec(dllexport) const char* NAME="C2077 Exact Shader Lab";
extern "C" __declspec(dllexport) const char* DESCRIPTION="One exact-bytecode DX12 shader only; observe/control/canary. Not a performance optimization.";
extern "C" __declspec(dllexport) bool AddonInit(HMODULE addon,HMODULE reshade_module) {
    bool registered=false;
    try {
        if(!host_allowed())return false;
        wchar_t path[MAX_PATH];DWORD length=GetModuleFileNameW(addon,path,MAX_PATH);if(!length||length>=MAX_PATH)return false;
        fs::path base=fs::path(path).parent_path();
        std::ifstream config(base/L"mode.txt",std::ios::binary);char buffer[65];config.read(buffer,sizeof(buffer));
        std::string text(buffer,static_cast<size_t>(config.gcount()));
        if(text.size()>64 || !parse_mode(text,mode))return false;
        if(!reshade::register_addon(addon,reshade_module))return false;
        registered=true;
        FILETIME ft;GetSystemTimeAsFileTime(&ft);ULARGE_INTEGER tick;tick.LowPart=ft.dwLowDateTime;tick.HighPart=ft.dwHighDateTime;
        fs::path log=base/(L"runtime-"+std::to_wstring(GetCurrentProcessId())+L"-"+std::to_wstring(tick.QuadPart)+L".jsonl");
        log_file=CreateFileW(log.c_str(),GENERIC_WRITE,FILE_SHARE_READ|FILE_SHARE_DELETE,nullptr,CREATE_NEW,FILE_ATTRIBUTE_NORMAL,nullptr);
        if(log_file==INVALID_HANDLE_VALUE){reshade::unregister_addon(addon);return false;}
        reshade::register_event<reshade::addon_event::init_pipeline>(on_init);
        reshade::register_event<reshade::addon_event::bind_pipeline>(on_bind);
        reshade::register_event<reshade::addon_event::destroy_pipeline>(on_destroy);
        reshade::register_event<reshade::addon_event::present>(on_present);
        enabled=true;snapshot("loaded_exe_guard_pass");
        reshade::log::message(reshade::log::level::info,"C2077 shader lab enabled with exact game path/SHA and shader bytecode guards.");
        return true;
    }catch(...){enabled=false;if(registered)reshade::unregister_addon(addon);return false;}
}
extern "C" __declspec(dllexport) void AddonUninit(HMODULE addon,HMODULE) {
    enabled=false;
    reshade::unregister_addon(addon);
    snapshot("unloaded");
    std::lock_guard<std::mutex> lock(log_mutex);
    if(log_file!=INVALID_HANDLE_VALUE){CloseHandle(log_file);log_file=INVALID_HANDLE_VALUE;}
}
BOOL WINAPI DllMain(HMODULE,DWORD,LPVOID){return TRUE;}

#ifdef SHADER_LAB_SELFTEST
int main() {
    Mode result;assert(parse_mode("control\r\n",result)&&result==Mode::control);assert(!parse_mode("unknown",result));
    shader_desc source;source.code=kOriginal;source.code_size=sizeof(kOriginal);
    assert(source_matches(source));shader_desc empty;assert(!source_matches(empty));
    auto bad=std::vector<unsigned char>(kOriginal,kOriginal+sizeof(kOriginal));bad[100]^=1;shader_desc wrong=source;wrong.code=bad.data();assert(!source_matches(wrong));
    pipeline_subobject objects[2];objects[0].type=pipeline_subobject_type::vertex_shader;objects[0].count=1;objects[0].data=&source;
    objects[1].type=pipeline_subobject_type::pixel_shader;objects[1].count=1;objects[1].data=&source;
    std::vector<pipeline_subobject> copy;shader_desc replacement;
    mode=Mode::control;assert(prepare_override(2,objects,copy,replacement));assert(replacement.code==kControl && replacement.code_size==sizeof(kControl));assert(copy[0].data==objects[0].data && source.code==kOriginal);
    mode=Mode::canary;assert(prepare_override(2,objects,copy,replacement));assert(replacement.code==kCanary && replacement.code_size==sizeof(kCanary));
    mode=Mode::observe;assert(!prepare_override(2,objects,copy,replacement));
    mode=Mode::control;assert(!prepare_override(1,objects,copy,replacement));
    objects[0].type=pipeline_subobject_type::pixel_shader;assert(!prepare_override(2,objects,copy,replacement));objects[0].type=pipeline_subobject_type::vertex_shader;
    objects[1].data=&wrong;assert(!prepare_override(2,objects,copy,replacement));objects[1].data=nullptr;assert(!prepare_override(2,objects,copy,replacement));assert(!prepare_override(0,nullptr,copy,replacement));
    auto truncated=source;truncated.code_size--;assert(!source_matches(truncated));assert(!parse_mode("",result));
    assert(!host_allowed());assert(!AddonInit(GetModuleHandleW(nullptr),nullptr));
    puts("Shader lab guards/descriptor cloning/negative host selfcheck PASS");
}
#endif
