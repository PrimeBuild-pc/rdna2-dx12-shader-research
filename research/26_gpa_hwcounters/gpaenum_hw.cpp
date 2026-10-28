// Phase 2O prep - does kGpaOpenContextEnableHardwareCountersBit expose raw counters that the
// default context hides? Specifically: any SQ/TA/TD counter that could discriminate pixel-stage
// ALU or texture-filter rate, which research/25_gpa_validity/GPA_VALIDITY.md showed the 145
// derived counters cannot.
//
// Uses the OFFLINE counter library virtual context: no D3D12 device, no GPU workload, no
// rendering. Enumerates once with default flags and once with the hardware-counter bit, then
// reports the difference.
//
//   gpaenum_hw.exe <outdir>

#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <cstdio>
#include <map>
#include <set>
#include <string>
#include <vector>
#include "gpu_performance_api/gpu_perf_api_counters.h"

typedef GpaStatus (*PFN_Open)(GpaApiType, GpaSessionSampleType, GpaCounterContextHardwareInfo,
                              GpaOpenContextFlags, GpaCounterContext*);
typedef GpaStatus (*PFN_Close)(const GpaCounterContext);
typedef GpaStatus (*PFN_Num)(const GpaCounterContext, GpaUInt32*);
typedef GpaStatus (*PFN_Str)(const GpaCounterContext, GpaUInt32, const char**);
typedef GpaStatus (*PFN_Usage)(const GpaCounterContext, GpaUInt32, GpaUsageType*);
typedef GpaStatus (*PFN_Info)(const GpaCounterContext, GpaUInt32, const GpaCounterInfo**);
typedef GpaStatus (*PFN_Passes)(const GpaCounterContext, const GpaUInt32*, GpaUInt32, GpaUInt32*);

static PFN_Open  Open;
static PFN_Close Close;
static PFN_Num   Num;
static PFN_Str   Name, Group, Desc;
static PFN_Usage Usage;
static PFN_Info  Info;
static PFN_Passes Passes;

static const char* kBlock[] = {
    "CPF","IA","VGT","PA","SC","SPI","SQ","SX","TA","TD","TCP","TCC","TCA","DB","CB","GDS",
    "SRBM","GRBM","GRBMSE","RLC","DMA","MC","CPG","CPC","WD","TCS","ATC","ATCL2","MCVML2","EA",
    "RPB","RMI","UMCCH","GE","GL1A","GL1C","GL1CG","GL2A","GL2C","CHA","CHC","CHCG","GUS","GCR",
    "PH","UTCL1","GEDIST","GESE","DFMALL","SQWGP","PC","GL1XA","GL1XC","WGS","EA_CPWD","EA_SE" };
static const char* kMask[] = { "PS","VS","GS","ES","HS","LS","CS","ALL" };
static const char* kUsage[] = { "ratio","percentage","cycles","milliseconds","bytes","items",
                                "kilobytes","nanoseconds" };

static const char* Lookup(const char* const* table, size_t n, unsigned i)
{
    return i < n ? table[i] : "?";
}

struct Counter
{
    std::string name, group, desc, usage, kind, block, mask;
    unsigned instance = 0, event = 0;
};

// Enumerate a virtual context opened with the given flags. Returns false with a printed reason.
static bool Enumerate(GpaOpenContextFlags flags, const char* label, std::vector<Counter>& out)
{
    GpaHardwareAttribute attrs[1];  // none supplied: the SDK keys the tables off the device id
    GpaCounterContextHardwareInfo hw = {};
    hw.vendor_id = 0x1002;    // AMD, from research/00_inventory/gpu_info.json
    hw.device_id = 0x73A5;    // Navi 21 (RX 6950 XT)
    hw.revision_id = 0xC0;
    hw.gpa_hardware_attributes = attrs;
    hw.gpa_hardware_attribute_count = 0;

    GpaCounterContext ctx = nullptr;
    GpaStatus st = Open(kGpaApiDirectx12, kGpaSessionSampleTypeDiscreteCounter, hw, flags, &ctx);
    if (st != kGpaStatusOk)
    {
        printf("%-10s GpaCounterLibOpenCounterContext KO, status %d\n", label, (int)st);
        return false;
    }
    GpaUInt32 n = 0;
    if (Num(ctx, &n) != kGpaStatusOk) { printf("%-10s GetNumCounters KO\n", label); return false; }

    for (GpaUInt32 i = 0; i < n; ++i)
    {
        Counter c;
        const char* s = nullptr;
        if (Name(ctx, i, &s) == kGpaStatusOk && s) c.name = s;
        if (Group(ctx, i, &s) == kGpaStatusOk && s) c.group = s;
        if (Desc(ctx, i, &s) == kGpaStatusOk && s) c.desc = s;
        GpaUsageType u;
        if (Usage(ctx, i, &u) == kGpaStatusOk) c.usage = Lookup(kUsage, 8, (unsigned)u);

        const GpaCounterInfo* ci = nullptr;
        if (Info(ctx, i, &ci) == kGpaStatusOk && ci)
        {
            c.kind = ci->is_derived_counter ? "derived" : "hardware";
            if (!ci->is_derived_counter && ci->gpa_hw_counter)
            {
                const GpaHwCounter* h = ci->gpa_hw_counter;
                if (h->is_timing_block)
                    c.block = "TIMESTAMP";
                else
                {
                    c.block = Lookup(kBlock, sizeof(kBlock)/sizeof(*kBlock),
                                     (unsigned)h->gpa_hw_block);
                    c.instance = h->gpa_hw_block_instance;
                    c.event = h->gpa_hw_block_event_id;
                    c.mask = Lookup(kMask, 8, (unsigned)h->gpa_shader_mask);
                }
            }
        }
        else
        {
            c.kind = "unknown";
        }
        out.push_back(c);
    }
    GpaUInt32 passes = 0;
    std::vector<GpaUInt32> all(n);
    for (GpaUInt32 i = 0; i < n; ++i) all[i] = i;
    GpaStatus ps = Passes(ctx, all.data(), n, &passes);
    printf("%-10s flags 0x%04X -> %u counters (all-counter pass count: %s%u)\n",
           label, (unsigned)flags, n, ps == kGpaStatusOk ? "" : "query failed, ", passes);
    Close(ctx);
    return true;
}

static void WriteCsv(const std::string& path, const std::vector<Counter>& v)
{
    FILE* f = nullptr;
    if (fopen_s(&f, path.c_str(), "w") != 0 || !f) { printf("cannot write %s\n", path.c_str()); return; }
    fprintf(f, "index,name,kind,group,block,instance,event_id,shader_mask,usage,description\n");
    for (size_t i = 0; i < v.size(); ++i)
    {
        std::string d = v[i].desc;
        for (auto& ch : d) if (ch == '"') ch = '\'';
        fprintf(f, "%zu,%s,%s,%s,%s,%u,%u,%s,%s,\"%s\"\n", i, v[i].name.c_str(), v[i].kind.c_str(),
                v[i].group.c_str(), v[i].block.c_str(), v[i].instance, v[i].event,
                v[i].mask.c_str(), v[i].usage.c_str(), d.c_str());
    }
    fclose(f);
    printf("wrote %s (%zu rows)\n", path.c_str(), v.size());
}

// Pass count for a named set. This is the number that decides whether finding A03 (each pass
// running a different frame) reappears, so it is measured rather than assumed.
static int PassesForNames(const char* listPath)
{
    FILE* f = nullptr;
    if (fopen_s(&f, listPath, "r") != 0 || !f) { printf("cannot read %s\n", listPath); return 1; }
    std::set<std::string> want;
    char line[512];
    while (fgets(line, sizeof(line), f))
    {
        std::string s(line);
        while (!s.empty() && (s.back() == '\n' || s.back() == '\r' || s.back() == ' ')) s.pop_back();
        if (!s.empty() && s[0] != '#') want.insert(s);
    }
    fclose(f);

    GpaHardwareAttribute attrs[1];
    GpaCounterContextHardwareInfo hw = {};
    hw.vendor_id = 0x1002; hw.device_id = 0x73A5; hw.revision_id = 0xC0;
    hw.gpa_hardware_attributes = attrs; hw.gpa_hardware_attribute_count = 0;
    GpaCounterContext ctx = nullptr;
    if (Open(kGpaApiDirectx12, kGpaSessionSampleTypeDiscreteCounter, hw,
             kGpaOpenContextEnableHardwareCountersBit, &ctx) != kGpaStatusOk)
    { printf("open KO\n"); return 1; }

    GpaUInt32 n = 0;
    Num(ctx, &n);
    std::vector<GpaUInt32> idx;
    std::set<std::string> found;
    for (GpaUInt32 i = 0; i < n; ++i)
    {
        const char* s = nullptr;
        if (Name(ctx, i, &s) == kGpaStatusOk && s && want.count(s)) { idx.push_back(i); found.insert(s); }
    }
    for (const auto& w : want)
        if (!found.count(w)) printf("  NOT FOUND: %s\n", w.c_str());

    GpaUInt32 passes = 0;
    GpaStatus st = Passes(ctx, idx.data(), (GpaUInt32)idx.size(), &passes);
    printf("%s: %zu/%zu counters resolved -> ", listPath, idx.size(), want.size());
    if (st == kGpaStatusOk) printf("%u pass(es)\n", passes);
    else printf("GpaCounterLibGetPassCount KO, status %d\n", (int)st);
    Close(ctx);
    return st == kGpaStatusOk ? 0 : 1;
}

// Which raw counters each derived counter is built from. This is the SDK's own statement of how
// raw events aggregate into a documented quantity, so it can be used to validate an aggregation
// formula empirically instead of guessing one.
static int Compose(const char* outPath)
{
    GpaHardwareAttribute attrs[1];
    GpaCounterContextHardwareInfo hw = {};
    hw.vendor_id = 0x1002; hw.device_id = 0x73A5; hw.revision_id = 0xC0;
    hw.gpa_hardware_attributes = attrs; hw.gpa_hardware_attribute_count = 0;
    GpaCounterContext ctx = nullptr;
    if (Open(kGpaApiDirectx12, kGpaSessionSampleTypeDiscreteCounter, hw,
             kGpaOpenContextEnableHardwareCountersBit, &ctx) != kGpaStatusOk)
    { printf("open KO\n"); return 1; }

    GpaUInt32 n = 0;
    Num(ctx, &n);
    // Raw counters are identified by (block, instance, event, mask); map that back to a name.
    std::map<std::string, std::string> rawName;
    std::vector<std::string> names(n);
    for (GpaUInt32 i = 0; i < n; ++i)
    {
        const char* s = nullptr;
        if (Name(ctx, i, &s) == kGpaStatusOk && s) names[i] = s;
        const GpaCounterInfo* ci = nullptr;
        if (Info(ctx, i, &ci) == kGpaStatusOk && ci && !ci->is_derived_counter && ci->gpa_hw_counter)
        {
            const GpaHwCounter* h = ci->gpa_hw_counter;
            char key[128];
            if (h->is_timing_block) sprintf_s(key, "T:%u", h->gpu_time_top_to_bottom_duration);
            else sprintf_s(key, "%u:%u:%u:%u", (unsigned)h->gpa_hw_block, h->gpa_hw_block_instance,
                           h->gpa_hw_block_event_id, (unsigned)h->gpa_shader_mask);
            rawName[key] = names[i];
        }
    }

    FILE* f = nullptr;
    if (fopen_s(&f, outPath, "w") != 0 || !f) { printf("cannot write %s\n", outPath); return 1; }
    fprintf(f, "derived,raw_count,raw_counters\n");
    unsigned done = 0;
    for (GpaUInt32 i = 0; i < n; ++i)
    {
        const GpaCounterInfo* ci = nullptr;
        if (Info(ctx, i, &ci) != kGpaStatusOk || !ci || !ci->is_derived_counter) continue;
        const GpaDerivedCounterInfo* d = ci->gpa_derived_counter;
        if (!d) continue;
        fprintf(f, "%s,%u,\"", names[i].c_str(), d->gpa_hw_counter_count);
        for (GpaUInt32 k = 0; k < d->gpa_hw_counter_count; ++k)
        {
            const GpaHwCounter* h = &d->gpa_hw_counters[k];
            char key[128];
            if (h->is_timing_block) sprintf_s(key, "T:%u", h->gpu_time_top_to_bottom_duration);
            else sprintf_s(key, "%u:%u:%u:%u", (unsigned)h->gpa_hw_block, h->gpa_hw_block_instance,
                           h->gpa_hw_block_event_id, (unsigned)h->gpa_shader_mask);
            auto it = rawName.find(key);
            fprintf(f, "%s%s", k ? " " : "", it != rawName.end() ? it->second.c_str() : key);
        }
        fprintf(f, "\"\n");
        ++done;
    }
    fclose(f);
    printf("wrote %s (%u derived counters decomposed)\n", outPath, done);
    Close(ctx);
    return 0;
}

int main(int argc, char** argv)
{
    std::string dir = argc > 1 ? argv[1] : ".";

    HMODULE lib = LoadLibraryA("GPUPerfAPICounters-x64.dll");
    if (!lib) { printf("GPUPerfAPICounters-x64.dll not loaded (%lu)\n", GetLastError()); return 1; }
#define GET(v, n) v = (decltype(v))GetProcAddress(lib, n); if (!v) { printf("missing export %s\n", n); return 1; }
    GET(Open,   "GpaCounterLibOpenCounterContext");
    GET(Close,  "GpaCounterLibCloseCounterContext");
    GET(Num,    "GpaCounterLibGetNumCounters");
    GET(Name,   "GpaCounterLibGetCounterName");
    GET(Group,  "GpaCounterLibGetCounterGroup");
    GET(Desc,   "GpaCounterLibGetCounterDescription");
    GET(Usage,  "GpaCounterLibGetCounterUsageType");
    GET(Info,   "GpaCounterLibGetCounterInfo");
    GET(Passes, "GpaCounterLibGetPassCount");
#undef GET

    if (argc > 2 && std::string(argv[1]) == "passes") return PassesForNames(argv[2]);
    if (argc > 2 && std::string(argv[1]) == "compose") return Compose(argv[2]);

    std::vector<Counter> def, hw;
    bool okDef = Enumerate(kGpaOpenContextDefaultBit, "default", def);
    bool okHw = Enumerate(kGpaOpenContextEnableHardwareCountersBit, "hardware", hw);
    if (!okDef || !okHw) return 2;

    WriteCsv(dir + "/counters_default.csv", def);
    WriteCsv(dir + "/counters_hardware.csv", hw);

    std::set<std::string> defNames;
    for (const auto& c : def) defNames.insert(c.name);

    // What the hardware bit adds, and how those additions are distributed over hardware blocks.
    std::map<std::string, unsigned> byBlock;
    std::map<std::string, unsigned> byMask;
    unsigned added = 0, addedHw = 0;
    for (const auto& c : hw)
    {
        if (defNames.count(c.name)) continue;
        ++added;
        if (c.kind == "hardware")
        {
            ++addedHw;
            byBlock[c.block]++;
            if (!c.mask.empty()) byMask[c.block + ":" + c.mask]++;
        }
    }
    printf("\nnames present with the hardware bit but not by default: %u (%u of them raw)\n",
           added, addedHw);
    printf("added raw counters per hardware block:\n");
    for (const auto& kv : byBlock) printf("  %-10s %u\n", kv.first.c_str(), kv.second);

    printf("\nSQ / TA / TD detail (the blocks that could answer the ALU and filter questions):\n");
    for (const auto& kv : byMask)
        if (kv.first.rfind("SQ", 0) == 0 || kv.first.rfind("TA", 0) == 0 ||
            kv.first.rfind("TD", 0) == 0 || kv.first.rfind("SQWGP", 0) == 0)
            printf("  %-14s %u\n", kv.first.c_str(), kv.second);

    unsigned ps = 0;
    for (const auto& c : hw)
        if (c.kind == "hardware" && c.mask == "PS") ++ps;
    printf("\nraw counters scoped to the PS shader mask: %u\n", ps);
    return 0;
}
