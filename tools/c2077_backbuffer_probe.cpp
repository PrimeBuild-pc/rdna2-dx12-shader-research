// Read-only catalog of pixel-shader draw calls with RT0 equal to a DX12 swapchain buffer.
#define WIN32_LEAN_AND_MEAN
#define NOMINMAX
#include <reshade.hpp>
#include <bcrypt.h>
#include <atomic>
#include <cassert>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <map>
#include <memory>
#include <mutex>
#include <set>
#include <sstream>
#include <string>
#include <vector>
#include "shader_payloads.hpp"
#pragma comment(lib,"bcrypt.lib")
using namespace reshade::api;
namespace fs=std::filesystem;
using Key=std::pair<uintptr_t,uint64_t>;
struct ShaderInfo {
    uint64_t serial=0;std::string hash,shape;size_t bytes=0;bool announced=false;
    uint64_t direct=0,indexed=0,indirect=0,unknown=0,empty=0,triangles=0,queued=0;
};
using Info=std::shared_ptr<ShaderInfo>;
struct ListState {Info pso;bool explicit_pso=false;Key rt={0,0};std::set<Info> work;};
struct Catalog {
    std::map<Key,Info> psos;
    std::map<uintptr_t,ListState> lists;
    std::map<uintptr_t,std::set<Key>> swaps;
    std::set<Key> buffers;
    std::vector<Info> seen;
    uint64_t next=0,all_draws=0,rt_binds=0,bb_rt_binds=0,submissions=0,bundles_on_bb=0;
    void swap(uintptr_t id,const std::set<Key>& resources){
        auto old=swaps.find(id);if(old!=swaps.end())for(auto k:old->second)buffers.erase(k);
        swaps[id]=resources;buffers.insert(resources.begin(),resources.end());
    }
    void forget_swap(uintptr_t id){swap(id,{});swaps.erase(id);}
    void bind(uintptr_t list,Key pso){auto& s=lists[list];auto it=psos.find(pso);s.pso=it==psos.end()?Info{}:it->second;s.explicit_pso=true;}
    void rt(uintptr_t list,Key resource){lists[list].rt=resource;++rt_binds;if(buffers.count(resource))++bb_rt_binds;}
    Info draw(uintptr_t list,unsigned kind,bool nonempty,bool triangle){
        ++all_draws;auto it=lists.find(list);if(it==lists.end()||!it->second.pso||!buffers.count(it->second.rt))return {};
        auto p=it->second.pso;
        if(kind==0)++p->direct;else if(kind==1)++p->indexed;else if(kind==2)++p->indirect;else ++p->unknown;
        if(!nonempty)++p->empty;else{it->second.work.insert(p);if(triangle)++p->triangles;}
        if(p->announced)return {};p->announced=true;seen.push_back(p);return p;
    }
    void submit(uintptr_t list){++submissions;auto it=lists.find(list);if(it!=lists.end())for(auto& p:it->second.work)++p->queued;}
    void secondary(uintptr_t primary,uintptr_t secondary){
        if(buffers.count(lists[primary].rt))++bundles_on_bb;
        auto s=lists.find(secondary);if(s!=lists.end()&&s->second.explicit_pso){lists[primary].pso=s->second.pso;lists[primary].explicit_pso=true;}
        // Inherited-RT bundle draws are a coverage gap, not silently attributed to a shader.
    }
    void reset(uintptr_t list){lists.erase(list);}
};
static Catalog catalog;
static std::mutex state_mutex,log_mutex;
static std::atomic<bool> enabled=false;
static std::atomic<ULONGLONG> last_report=0;
static HANDLE logfile=INVALID_HANDLE_VALUE;
static bool dx12(command_list* list){return list&&list->get_device()->get_api()==device_api::d3d12;}
static std::string hex(const unsigned char* data,size_t size){const char* digits="0123456789abcdef";std::string s;for(size_t i=0;i<size;++i){s+=digits[data[i]>>4];s+=digits[data[i]&15];}return s;}
static bool digest(const void* data,size_t size,std::string& result){
    if(!data||!size||size>128*1024*1024)return false;unsigned char hash[32];
    if(BCryptHash(BCRYPT_SHA256_ALG_HANDLE,nullptr,0,const_cast<PUCHAR>(static_cast<const unsigned char*>(data)),static_cast<ULONG>(size),hash,32)<0)return false;
    result=hex(hash,32);return true;
}
static void write_line(const std::string& body) noexcept {
    try{std::string line="{\"schema\":1,\"experiment\":\"C2077-BACKBUFFER-PROBE-001\",\"pid\":"+std::to_string(GetCurrentProcessId())+","+body+"}\n";
        std::lock_guard<std::mutex> lock(log_mutex);if(logfile!=INVALID_HANDLE_VALUE){DWORD n;WriteFile(logfile,line.data(),static_cast<DWORD>(line.size()),&n,nullptr);FlushFileBuffers(logfile);}}
    catch(...){}
}
static void snapshot(const char* event) noexcept {
    try{
        std::vector<std::string> rows;
        {std::lock_guard<std::mutex> lock(state_mutex);
            std::ostringstream out;out<<"\"event\":\""<<event<<"\",\"known_buffers\":"<<catalog.buffers.size()<<",\"known_pixel_psos\":"<<catalog.psos.size()
            <<",\"all_draw_callbacks\":"<<catalog.all_draws<<",\"rt_binds\":"<<catalog.rt_binds<<",\"bb_rt_binds\":"<<catalog.bb_rt_binds
            <<",\"queue_submissions\":"<<catalog.submissions<<",\"bundle_calls_on_bb\":"<<catalog.bundles_on_bb<<",\"candidates\":"<<catalog.seen.size();rows.push_back(out.str());
            for(auto& p:catalog.seen){std::ostringstream s;s<<"\"event\":\"candidate_stats\",\"serial\":"<<p->serial<<",\"shader_sha256\":\""<<p->hash<<"\",\"direct\":"<<p->direct
                <<",\"indexed\":"<<p->indexed<<",\"indirect\":"<<p->indirect<<",\"unknown_indirect\":"<<p->unknown<<",\"empty\":"<<p->empty
                <<",\"fullscreen_triangle_calls\":"<<p->triangles<<",\"queued_list_references\":"<<p->queued;rows.push_back(s.str());}}
        for(size_t i=1;i<rows.size();++i)write_line(rows[i]);
        if(!rows.empty())write_line(rows[0]);
    }catch(...){enabled=false;}
}
static void on_init(device* d,pipeline_layout,uint32_t count,const pipeline_subobject* objects,pipeline pso) noexcept {
    if(!enabled||d->get_api()!=device_api::d3d12||!objects||count>256||!pso.handle)return;
    try{
        Info info;std::ostringstream shape;
        for(uint32_t i=0;i<count;++i){auto& o=objects[i];
            if(o.type==pipeline_subobject_type::pixel_shader&&o.count==1&&o.data){auto& ps=*static_cast<const shader_desc*>(o.data);if(ps.code_size<32||ps.code_size>16*1024*1024||!ps.code||memcmp(ps.code,"DXBC",4)!=0)continue;
                info=std::make_shared<ShaderInfo>();if(!digest(ps.code,ps.code_size,info->hash))return;info->bytes=ps.code_size;}
            else if(o.type==pipeline_subobject_type::render_target_formats&&o.count<=8&&(o.data||o.count==0)){shape<<",\"rt_count\":"<<o.count;if(o.count)shape<<",\"rt0_format\":"<<static_cast<uint32_t>(*static_cast<const format*>(o.data));}
            else if(o.type==pipeline_subobject_type::blend_state&&o.count==1&&o.data){auto& b=*static_cast<const blend_desc*>(o.data);shape<<",\"rt0_write_mask\":"<<unsigned(b.render_target_write_mask[0])<<",\"blend_enable\":"<<b.blend_enable[0]<<",\"src_rgb\":"<<static_cast<uint32_t>(b.source_color_blend_factor[0])<<",\"dst_rgb\":"<<static_cast<uint32_t>(b.dest_color_blend_factor[0]);}
            else if(o.type==pipeline_subobject_type::depth_stencil_state&&o.count==1&&o.data)shape<<",\"depth_enable\":"<<static_cast<const depth_stencil_desc*>(o.data)->depth_enable;
        }
        if(info){info->shape=shape.str();std::lock_guard<std::mutex> lock(state_mutex);Key key{reinterpret_cast<uintptr_t>(d),pso.handle};auto old=catalog.psos.find(key);if(old!=catalog.psos.end()&&old->second->hash==info->hash&&old->second->shape==info->shape)return;info->serial=++catalog.next;catalog.psos[key]=info;}
    }catch(...){enabled=false;}
}
static void on_destroy_pso(device* d,pipeline pso) noexcept {try{std::lock_guard<std::mutex> lock(state_mutex);catalog.psos.erase({reinterpret_cast<uintptr_t>(d),pso.handle});}catch(...){enabled=false;}}
static void on_swap(swapchain* swap,bool) noexcept {
    if(!enabled||swap->get_device()->get_api()!=device_api::d3d12)return;
    try{
        std::set<Key> buffers;auto* d=swap->get_device();uint32_t count=swap->get_back_buffer_count();if(count>16)return;
        for(uint32_t i=0;i<count;++i){auto r=swap->get_back_buffer(i);if(!r.handle)continue;buffers.insert({reinterpret_cast<uintptr_t>(d),r.handle});auto desc=d->get_resource_desc(r);
            std::ostringstream s;s<<"\"event\":\"backbuffer\",\"resource\":"<<r.handle<<",\"width\":"<<desc.texture.width<<",\"height\":"<<desc.texture.height<<",\"format\":"<<static_cast<uint32_t>(desc.texture.format);write_line(s.str());}
        std::lock_guard<std::mutex> lock(state_mutex);catalog.swap(reinterpret_cast<uintptr_t>(swap),buffers);
    }catch(...){enabled=false;}
}
static void on_destroy_swap(swapchain* swap,bool) noexcept {try{std::lock_guard<std::mutex> lock(state_mutex);catalog.forget_swap(reinterpret_cast<uintptr_t>(swap));}catch(...){enabled=false;}}
static void on_bind(command_list* list,pipeline_stage stages,pipeline pso) noexcept {
    if(!enabled||!dx12(list)||(static_cast<uint32_t>(stages)&static_cast<uint32_t>(pipeline_stage::pixel_shader))==0)return;
    try{std::lock_guard<std::mutex> lock(state_mutex);catalog.bind(reinterpret_cast<uintptr_t>(list),{reinterpret_cast<uintptr_t>(list->get_device()),pso.handle});}catch(...){enabled=false;}
}
static void on_rt(command_list* list,uint32_t count,const resource_view* views,resource_view) noexcept {
    if(!enabled||!dx12(list))return;
    try{auto* d=list->get_device();resource r={0};if(count&&views&&views[0].handle)r=d->get_resource_from_view(views[0]);std::lock_guard<std::mutex> lock(state_mutex);catalog.rt(reinterpret_cast<uintptr_t>(list),{reinterpret_cast<uintptr_t>(d),r.handle});}catch(...){enabled=false;}
}
static bool on_pass(command_list* list,uint32_t count,const render_pass_render_target_desc* rts,const render_pass_depth_stencil_desc*,render_pass_flags) noexcept {
    resource_view first=count&&rts?rts[0].view:resource_view{0};on_rt(list,count,&first,{0});return false;
}
static void record(command_list* list,unsigned kind,bool nonempty,bool triangle=false) noexcept {
    if(!enabled||!dx12(list))return;
    try{Info info;Key rt;{std::lock_guard<std::mutex> lock(state_mutex);info=catalog.draw(reinterpret_cast<uintptr_t>(list),kind,nonempty,triangle);if(info)rt=catalog.lists[reinterpret_cast<uintptr_t>(list)].rt;}
        if(info){std::ostringstream s;s<<"\"event\":\"candidate\",\"serial\":"<<info->serial<<",\"shader_sha256\":\""<<info->hash<<"\",\"shader_bytes\":"<<info->bytes<<",\"backbuffer_resource\":"<<rt.second<<info->shape;write_line(s.str());}}
    catch(...){enabled=false;}
}
static bool on_draw(command_list* l,uint32_t n,uint32_t instances,uint32_t,uint32_t) noexcept {record(l,0,n>0&&instances>0,n==3&&instances==1);return false;}
static bool on_indexed(command_list* l,uint32_t n,uint32_t instances,uint32_t,int32_t,uint32_t) noexcept {record(l,1,n>0&&instances>0);return false;}
static bool on_indirect(command_list* l,indirect_command type,resource,uint64_t,uint32_t count,uint32_t) noexcept {
    if(type==indirect_command::draw||type==indirect_command::draw_indexed)record(l,2,count>0);else if(type==indirect_command::unknown)record(l,3,count>0);return false;
}
static void on_reset(command_list* l) noexcept {try{std::lock_guard<std::mutex> lock(state_mutex);catalog.reset(reinterpret_cast<uintptr_t>(l));}catch(...){enabled=false;}}
static void on_submit(command_queue*,command_list* l) noexcept {if(!enabled||!dx12(l))return;try{std::lock_guard<std::mutex> lock(state_mutex);catalog.submit(reinterpret_cast<uintptr_t>(l));}catch(...){enabled=false;}}
static void on_secondary(command_list* l,command_list* s) noexcept {if(!enabled||!dx12(l))return;try{std::lock_guard<std::mutex> lock(state_mutex);catalog.secondary(reinterpret_cast<uintptr_t>(l),reinterpret_cast<uintptr_t>(s));}catch(...){enabled=false;}}
static void on_present(command_queue*,swapchain*,const rect*,const rect*,uint32_t,const rect*) noexcept {if(!enabled)return;auto now=GetTickCount64(),last=last_report.load();if(now-last>=5000&&last_report.compare_exchange_strong(last,now))snapshot("heartbeat");}
static bool host_allowed(){
    wchar_t path[MAX_PATH];DWORD n=GetModuleFileNameW(nullptr,path,MAX_PATH);if(!n||n>=MAX_PATH||CompareStringOrdinal(path,-1,kExpectedGamePath,-1,TRUE)!=CSTR_EQUAL)return false;
    std::ifstream f(fs::path(path),std::ios::binary|std::ios::ate);if(!f)return false;auto size=f.tellg();if(size<=0||size>128*1024*1024)return false;
    std::vector<unsigned char>b(static_cast<size_t>(size));f.seekg(0);f.read(reinterpret_cast<char*>(b.data()),b.size());if(!f)return false;std::string h;return digest(b.data(),b.size(),h)&&h==hex(kExpectedGameSha,32);
}
extern "C" __declspec(dllexport) const char* NAME="C2077 Backbuffer Shader Catalog";
extern "C" __declspec(dllexport) const char* DESCRIPTION="Readonly draw/RT0/backbuffer correlation; no shader replacement or GPU timing.";
extern "C" __declspec(dllexport) bool AddonInit(HMODULE addon,HMODULE host){
    bool registered=false;try{if(!host_allowed()||!reshade::register_addon(addon,host))return false;registered=true;
        wchar_t path[MAX_PATH];DWORD n=GetModuleFileNameW(addon,path,MAX_PATH);if(!n||n>=MAX_PATH){reshade::unregister_addon(addon);return false;}
        FILETIME ft;GetSystemTimeAsFileTime(&ft);ULARGE_INTEGER t;t.LowPart=ft.dwLowDateTime;t.HighPart=ft.dwHighDateTime;
        auto p=fs::path(path).parent_path()/(L"backbuffer-"+std::to_wstring(GetCurrentProcessId())+L"-"+std::to_wstring(t.QuadPart)+L".jsonl");
        logfile=CreateFileW(p.c_str(),GENERIC_WRITE,FILE_SHARE_READ|FILE_SHARE_DELETE,nullptr,CREATE_NEW,FILE_ATTRIBUTE_NORMAL,nullptr);if(logfile==INVALID_HANDLE_VALUE){reshade::unregister_addon(addon);return false;}
#define EVENT(name,fn) reshade::register_event<reshade::addon_event::name>(fn)
        EVENT(init_pipeline,on_init);EVENT(destroy_pipeline,on_destroy_pso);EVENT(init_swapchain,on_swap);EVENT(destroy_swapchain,on_destroy_swap);
        EVENT(bind_pipeline,on_bind);EVENT(bind_render_targets_and_depth_stencil,on_rt);EVENT(begin_render_pass,on_pass);
        EVENT(draw,on_draw);EVENT(draw_indexed,on_indexed);EVENT(draw_or_dispatch_indirect,on_indirect);
        EVENT(reset_command_list,on_reset);EVENT(destroy_command_list,on_reset);EVENT(execute_command_list,on_submit);EVENT(execute_secondary_command_list,on_secondary);EVENT(present,on_present);
#undef EVENT
        enabled=true;snapshot("loaded_exe_guard_pass");return true;
    }catch(...){enabled=false;if(registered)reshade::unregister_addon(addon);return false;}
}
extern "C" __declspec(dllexport) void AddonUninit(HMODULE addon,HMODULE){enabled=false;reshade::unregister_addon(addon);snapshot("unloaded");std::lock_guard<std::mutex> lock(log_mutex);if(logfile!=INVALID_HANDLE_VALUE){CloseHandle(logfile);logfile=INVALID_HANDLE_VALUE;}}
BOOL WINAPI DllMain(HMODULE,DWORD,LPVOID){return TRUE;}
#ifdef BACKBUFFER_SELFTEST
int main(){
    Catalog c;auto p=std::make_shared<ShaderInfo>();p->hash="test";c.psos[{1,2}]=p;c.swap(10,{{1,99}});c.bind(20,{1,2});c.rt(20,{1,98});assert(!c.draw(20,0,true,true));
    c.rt(20,{1,99});assert(c.draw(20,0,true,true)==p);assert(p->direct==1&&p->triangles==1);c.submit(20);assert(p->queued==1);
    c.bind(20,{1,3});assert(!c.draw(20,0,true,true));c.reset(20);c.submit(20);assert(p->queued==1);
    c.bind(20,{1,2});c.rt(20,{2,99});assert(!c.draw(20,1,true,false));c.swap(10,{{1,100}});c.rt(20,{1,99});assert(!c.draw(20,0,true,false));
    c.rt(20,{1,100});c.draw(20,1,false,false);assert(p->empty==1);c.submit(20);assert(p->queued==1);c.forget_swap(10);assert(c.buffers.empty());
    std::string h;assert(digest("abc",3,h)&&h=="ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad");std::vector<char> host_sized(17*1024*1024);assert(digest(host_sized.data(),host_sized.size(),h));assert(!host_allowed());assert(!AddonInit(GetModuleHandleW(nullptr),nullptr));assert(!on_draw(nullptr,0,0,0,0));
    puts("Backbuffer catalog correlation/resize/reset/device/empty/hash/host selfcheck PASS");
}
#endif
