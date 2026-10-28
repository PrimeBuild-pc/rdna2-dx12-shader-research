// Observes only the original glass shader. Never changes pipelines, draws or GPU resources.
#define WIN32_LEAN_AND_MEAN
#define NOMINMAX
#include <reshade.hpp>
#include <bcrypt.h>
#include <cassert>
#include <atomic>
#include <cstdio>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <map>
#include <mutex>
#include <set>
#include <sstream>
#include <string>
#include <vector>
#include "shader_payloads.hpp"
#pragma comment(lib,"bcrypt.lib")
using namespace reshade::api;
namespace fs=std::filesystem;
using PsoKey=std::pair<uintptr_t,uint64_t>;
struct ListState {bool target=false,binding_known=false;uint64_t work=0;};
struct Trace {
    std::set<PsoKey> targets;
    std::map<uintptr_t,ListState> lists;
    uint64_t inits=0,binds=0,all_draw_callbacks=0,direct=0,indexed=0,indirect=0,unknown_indirect=0,empty=0,bundles=0,submissions=0,target_work_submissions=0;
    void bind(PsoKey key,uintptr_t list){bool hit=targets.count(key)!=0;auto& s=lists[list];s.target=hit;s.binding_known=true;if(hit)++binds;}
    void draw(uintptr_t list,unsigned kind,bool nonempty){
        ++all_draw_callbacks;auto it=lists.find(list);if(it==lists.end()||!it->second.target)return;
        if(kind==0)++direct;else if(kind==1)++indexed;else if(kind==2)++indirect;else ++unknown_indirect;
        if(nonempty)++it->second.work;else ++empty;
    }
    void secondary(uintptr_t primary,uintptr_t secondary){
        auto p=lists.find(primary),s=lists.find(secondary);
        bool inherited=p!=lists.end()&&p->second.target;
        bool recorded=s!=lists.end()&&s->second.work>0;
        if(inherited||recorded){++bundles;++lists[primary].work;}
        if(s!=lists.end()&&s->second.binding_known){auto& end=lists[primary];end.target=s->second.target;end.binding_known=true;}
    }
    void submit(uintptr_t list){++submissions;auto it=lists.find(list);if(it!=lists.end()&&it->second.work>0)++target_work_submissions;}
    void reset(uintptr_t list){lists.erase(list);}
};
static Trace trace;
static std::mutex state_mutex,log_mutex;
static HANDLE logfile=INVALID_HANDLE_VALUE;
static std::atomic<bool> enabled=false;
static std::atomic<ULONGLONG> last_report=0;
static bool is_dx12(command_list* list){return list&&list->get_device()->get_api()==device_api::d3d12;}
static void write_line(const std::string& body) noexcept {
    try {
        std::string line="{\"schema\":1,\"experiment\":\"C2077-SHADER-PROBE-001\",\"pid\":"+std::to_string(GetCurrentProcessId())+","+body+"}\n";
        std::lock_guard<std::mutex> lock(log_mutex);
        if(logfile!=INVALID_HANDLE_VALUE){DWORD written;WriteFile(logfile,line.data(),static_cast<DWORD>(line.size()),&written,nullptr);FlushFileBuffers(logfile);}
    }catch(...){}
}
static void snapshot(const char* event) noexcept {
    try {
        std::ostringstream out;out<<"\"event\":\""<<event<<"\"";
        {std::lock_guard<std::mutex> lock(state_mutex);
        out<<",\"pipeline_inits\":"<<trace.inits<<",\"target_psos\":"<<trace.targets.size()<<",\"target_binds\":"<<trace.binds
           <<",\"all_draw_callbacks\":"<<trace.all_draw_callbacks<<",\"target_direct_calls\":"<<trace.direct
           <<",\"target_indexed_calls\":"<<trace.indexed<<",\"target_indirect_calls\":"<<trace.indirect
           <<",\"target_unknown_indirect_calls\":"<<trace.unknown_indirect<<",\"target_empty_calls\":"<<trace.empty
           <<",\"target_bundle_potential_calls\":"<<trace.bundles<<",\"queue_list_submissions\":"<<trace.submissions
           <<",\"target_work_list_submissions\":"<<trace.target_work_submissions;}
        write_line(out.str());
    }catch(...){enabled=false;}
}
static bool target_shader(uint32_t count,const pipeline_subobject* objects){
    if(!objects||count>256)return false;
    for(uint32_t i=0;i<count;++i)if(objects[i].type==pipeline_subobject_type::pixel_shader&&objects[i].count==1&&objects[i].data){
        const auto& s=*static_cast<const shader_desc*>(objects[i].data);
        if(s.code&&s.code_size==sizeof(kOriginal)&&memcmp(s.code,kOriginal,sizeof(kOriginal))==0)return true;
    }
    return false;
}
static std::string describe(uint32_t count,const pipeline_subobject* objects,uint64_t pso,uint64_t layout){
    std::ostringstream out;out<<"\"event\":\"target_pso\",\"pso\":"<<pso<<",\"layout\":"<<layout;
    bool blend_known=false,formats_known=false,depth_known=false;
    for(uint32_t i=0;i<count;++i){const auto& o=objects[i];if(!o.data&&!(o.type==pipeline_subobject_type::render_target_formats&&o.count==0))continue;
        if(o.type==pipeline_subobject_type::render_target_formats&&o.count<=8){
            formats_known=true;out<<",\"rt_count\":"<<o.count<<",\"rt_formats\":[";
            for(uint32_t k=0;k<o.count;++k){if(k)out<<",";out<<static_cast<uint32_t>(static_cast<const format*>(o.data)[k]);}out<<"]";
        }else if(o.type==pipeline_subobject_type::blend_state&&o.count==1){
            blend_known=true;auto& b=*static_cast<const blend_desc*>(o.data);out<<",\"render_targets\":[";
            for(unsigned k=0;k<8;++k){if(k)out<<",";out<<"{\"index\":"<<k<<",\"write_mask\":"<<unsigned(b.render_target_write_mask[k])
                <<",\"blend_enable\":"<<b.blend_enable[k]<<",\"src_rgb\":"<<static_cast<uint32_t>(b.source_color_blend_factor[k])
                <<",\"dst_rgb\":"<<static_cast<uint32_t>(b.dest_color_blend_factor[k])<<",\"rgb_op\":"<<static_cast<uint32_t>(b.color_blend_op[k])
                <<",\"src_alpha\":"<<static_cast<uint32_t>(b.source_alpha_blend_factor[k])<<",\"dst_alpha\":"<<static_cast<uint32_t>(b.dest_alpha_blend_factor[k])<<"}";}out<<"]";
        }else if(o.type==pipeline_subobject_type::depth_stencil_state&&o.count==1){
            depth_known=true;auto& d=*static_cast<const depth_stencil_desc*>(o.data);out<<",\"depth_enable\":"<<d.depth_enable<<",\"depth_write\":"<<d.depth_write_mask<<",\"depth_func\":"<<static_cast<uint32_t>(d.depth_func)<<",\"stencil_enable\":"<<d.stencil_enable;
        }else if(o.type==pipeline_subobject_type::sample_mask&&o.count==1)out<<",\"sample_mask\":"<<*static_cast<const uint32_t*>(o.data);
    }
    out<<",\"blend_known\":"<<blend_known<<",\"formats_known\":"<<formats_known<<",\"depth_known\":"<<depth_known;
    return out.str();
}
static void on_init(device* d,pipeline_layout layout,uint32_t count,const pipeline_subobject* objects,pipeline pso) noexcept {
    if(!enabled||d->get_api()!=device_api::d3d12||!pso.handle)return;
    try {
        bool hit=target_shader(count,objects),inserted=false;
        {std::lock_guard<std::mutex> lock(state_mutex);++trace.inits;if(hit)inserted=trace.targets.insert({reinterpret_cast<uintptr_t>(d),pso.handle}).second;}
        if(inserted)write_line(describe(count,objects,pso.handle,layout.handle));
    }catch(...){enabled=false;}
}
static void on_bind(command_list* list,pipeline_stage stages,pipeline pso) noexcept {
    if(!enabled||!is_dx12(list)||(static_cast<uint32_t>(stages)&static_cast<uint32_t>(pipeline_stage::pixel_shader))==0)return;
    try{std::lock_guard<std::mutex> lock(state_mutex);trace.bind({reinterpret_cast<uintptr_t>(list->get_device()),pso.handle},reinterpret_cast<uintptr_t>(list));}catch(...){enabled=false;}
}
static void on_destroy_pso(device* d,pipeline pso) noexcept {
    try{std::lock_guard<std::mutex> lock(state_mutex);trace.targets.erase({reinterpret_cast<uintptr_t>(d),pso.handle});}catch(...){enabled=false;}
}
static void record(command_list* list,unsigned kind,bool nonempty) noexcept {
    if(!enabled||!is_dx12(list))return;
    try{std::lock_guard<std::mutex> lock(state_mutex);trace.draw(reinterpret_cast<uintptr_t>(list),kind,nonempty);}catch(...){enabled=false;}
}
static bool on_draw(command_list* list,uint32_t vertices,uint32_t instances,uint32_t,uint32_t) noexcept {record(list,0,vertices>0&&instances>0);return false;}
static bool on_indexed(command_list* list,uint32_t indices,uint32_t instances,uint32_t,int32_t,uint32_t) noexcept {record(list,1,indices>0&&instances>0);return false;}
static bool on_indirect(command_list* list,indirect_command type,resource,uint64_t,uint32_t count,uint32_t) noexcept {
    if(type==indirect_command::draw||type==indirect_command::draw_indexed)record(list,2,count>0);
    else if(type==indirect_command::unknown)record(list,3,count>0);
    return false;
}
static void on_reset(command_list* list) noexcept {try{std::lock_guard<std::mutex> lock(state_mutex);trace.reset(reinterpret_cast<uintptr_t>(list));}catch(...){enabled=false;}}
static void on_submit(command_queue*,command_list* list) noexcept {
    if(!enabled||!is_dx12(list))return;
    try{std::lock_guard<std::mutex> lock(state_mutex);trace.submit(reinterpret_cast<uintptr_t>(list));}catch(...){enabled=false;}
}
static void on_secondary(command_list* primary,command_list* secondary) noexcept {
    if(!enabled||!is_dx12(primary))return;
    try{std::lock_guard<std::mutex> lock(state_mutex);trace.secondary(reinterpret_cast<uintptr_t>(primary),reinterpret_cast<uintptr_t>(secondary));}catch(...){enabled=false;}
}
static void on_present(command_queue*,swapchain*,const rect*,const rect*,uint32_t,const rect*) noexcept {
    if(!enabled)return;auto now=GetTickCount64(),previous=last_report.load();
    if(now-previous>=5000&&last_report.compare_exchange_strong(previous,now))snapshot("heartbeat");
}
static bool host_allowed(){
    wchar_t path[MAX_PATH];DWORD n=GetModuleFileNameW(nullptr,path,MAX_PATH);
    if(!n||n>=MAX_PATH||CompareStringOrdinal(path,-1,kExpectedGamePath,-1,TRUE)!=CSTR_EQUAL)return false;
    std::ifstream f(fs::path(path),std::ios::binary|std::ios::ate);if(!f)return false;auto size=f.tellg();if(size<=0||size>128*1024*1024)return false;
    std::vector<unsigned char>b(static_cast<size_t>(size));f.seekg(0);f.read(reinterpret_cast<char*>(b.data()),b.size());if(!f)return false;unsigned char hash[32];
    return BCryptHash(BCRYPT_SHA256_ALG_HANDLE,nullptr,0,b.data(),static_cast<ULONG>(b.size()),hash,32)>=0&&memcmp(hash,kExpectedGameSha,32)==0;
}
extern "C" __declspec(dllexport) const char* NAME="C2077 Readonly Shader Probe";
extern "C" __declspec(dllexport) const char* DESCRIPTION="Original glass PSO masks and CPU draw/submission observations; no GPU timing or state changes.";
extern "C" __declspec(dllexport) bool AddonInit(HMODULE addon,HMODULE host){
    bool registered=false;
    try{
        if(!host_allowed()||!reshade::register_addon(addon,host))return false;registered=true;
        wchar_t path[MAX_PATH];DWORD n=GetModuleFileNameW(addon,path,MAX_PATH);if(!n||n>=MAX_PATH){reshade::unregister_addon(addon);return false;}
        FILETIME ft;GetSystemTimeAsFileTime(&ft);ULARGE_INTEGER t;t.LowPart=ft.dwLowDateTime;t.HighPart=ft.dwHighDateTime;
        auto p=fs::path(path).parent_path()/(L"probe-"+std::to_wstring(GetCurrentProcessId())+L"-"+std::to_wstring(t.QuadPart)+L".jsonl");
        logfile=CreateFileW(p.c_str(),GENERIC_WRITE,FILE_SHARE_READ|FILE_SHARE_DELETE,nullptr,CREATE_NEW,FILE_ATTRIBUTE_NORMAL,nullptr);
        if(logfile==INVALID_HANDLE_VALUE){reshade::unregister_addon(addon);return false;}
#define EVENT(name,fn) reshade::register_event<reshade::addon_event::name>(fn)
        EVENT(init_pipeline,on_init);EVENT(bind_pipeline,on_bind);EVENT(destroy_pipeline,on_destroy_pso);
        EVENT(draw,on_draw);EVENT(draw_indexed,on_indexed);EVENT(draw_or_dispatch_indirect,on_indirect);
        EVENT(reset_command_list,on_reset);EVENT(destroy_command_list,on_reset);
        EVENT(execute_command_list,on_submit);EVENT(execute_secondary_command_list,on_secondary);EVENT(present,on_present);
#undef EVENT
        enabled=true;snapshot("loaded_exe_guard_pass");return true;
    }catch(...){enabled=false;if(registered)reshade::unregister_addon(addon);return false;}
}
extern "C" __declspec(dllexport) void AddonUninit(HMODULE addon,HMODULE){
    enabled=false;reshade::unregister_addon(addon);snapshot("unloaded");
    std::lock_guard<std::mutex> lock(log_mutex);if(logfile!=INVALID_HANDLE_VALUE){CloseHandle(logfile);logfile=INVALID_HANDLE_VALUE;}
}
BOOL WINAPI DllMain(HMODULE,DWORD,LPVOID){return TRUE;}
#ifdef SHADER_PROBE_SELFTEST
int main(){
    Trace t;t.targets.insert({1,10});t.bind({1,10},50);t.draw(50,1,true);assert(t.indexed==1);t.submit(50);assert(t.target_work_submissions==1);
    t.bind({1,11},50);t.draw(50,1,true);assert(t.indexed==1);t.reset(50);t.submit(50);assert(t.target_work_submissions==1);
    t.bind({2,10},50);t.draw(50,0,true);assert(t.direct==0);t.bind({1,10},51);t.draw(51,2,true);assert(t.indirect==1);t.secondary(52,51);t.submit(52);assert(t.target_work_submissions==2);
    t.bind({1,11},51);t.secondary(52,51);t.draw(52,0,true);assert(t.direct==0);
    t.reset(51);t.draw(51,0,true);assert(t.direct==0);t.bind({1,10},51);t.draw(51,0,false);assert(t.empty==1);t.submit(51);assert(t.target_work_submissions==2);
    shader_desc ps;ps.code=kOriginal;ps.code_size=sizeof(kOriginal);pipeline_subobject obj{pipeline_subobject_type::pixel_shader,1,&ps};assert(target_shader(1,&obj));obj.type=pipeline_subobject_type::vertex_shader;assert(!target_shader(1,&obj));assert(!target_shader(0,nullptr));
    blend_desc b;b.render_target_write_mask[0]=0;pipeline_subobject blend{pipeline_subobject_type::blend_state,1,&b};auto json=describe(1,&blend,1,2);assert(json.find("\"write_mask\":0")!=std::string::npos);assert(json.find("\"formats_known\":0")!=std::string::npos);
    pipeline_subobject no_color{pipeline_subobject_type::render_target_formats,0,nullptr};auto zero=describe(1,&no_color,1,2);assert(zero.find("\"rt_count\":0")!=std::string::npos&&zero.find("\"formats_known\":1")!=std::string::npos);
    assert(!host_allowed());assert(!AddonInit(GetModuleHandleW(nullptr),nullptr));assert(!on_draw(nullptr,0,0,0,0));
    puts("Readonly probe state/overwrite/reset/submit/bundle/masks/host guards selfcheck PASS");
}
#endif
