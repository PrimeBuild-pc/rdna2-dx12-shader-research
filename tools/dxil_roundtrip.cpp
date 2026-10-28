// Offline DXIL assembly/validation through the installed Microsoft SDK only.
#include <windows.h>
#include <dxcapi.h>
#include <wrl/client.h>
#include <cstdio>
#include <stdexcept>
#include <string>
using Microsoft::WRL::ComPtr;

static void checked(HRESULT hr, const char* step) {
    printf("%s_hresult=0x%08lx\n",step,static_cast<unsigned long>(hr));
    if (FAILED(hr)) throw std::runtime_error(step);
}
static ComPtr<IDxcBlob> result(IDxcOperationResult* operation, const char* step) {
    HRESULT status=E_FAIL;
    checked(operation->GetStatus(&status),"GetStatus");
    ComPtr<IDxcBlobEncoding> errors;
    checked(operation->GetErrorBuffer(&errors),"GetErrorBuffer");
    if (errors && errors->GetBufferSize())
        fwrite(errors->GetBufferPointer(),1,errors->GetBufferSize(),stderr);
    checked(status,step);
    ComPtr<IDxcBlob> blob;
    checked(operation->GetResult(&blob),"GetResult");
    return blob;
}
static void write_new(const wchar_t* path, IDxcBlob* blob) {
    if (!blob || !blob->GetBufferSize() || blob->GetBufferSize()>MAXDWORD)
        throw std::runtime_error("empty/oversized output");
    HANDLE file=CreateFileW(path,GENERIC_WRITE,0,nullptr,CREATE_NEW,FILE_ATTRIBUTE_NORMAL,nullptr);
    if (file==INVALID_HANDLE_VALUE) throw std::runtime_error("cannot create new output");
    DWORD size=static_cast<DWORD>(blob->GetBufferSize()),written=0;
    BOOL ok=WriteFile(file,blob->GetBufferPointer(),size,&written,nullptr);
    if (ok && written==size) ok=FlushFileBuffers(file);
    BOOL closed=CloseHandle(file);
    if (!ok || written!=size || !closed) throw std::runtime_error("incomplete output write");
}
static int work(bool assemble, HMODULE compiler, HMODULE validation, wchar_t** argv) {
    auto create=reinterpret_cast<DxcCreateInstanceProc>(GetProcAddress(compiler,"DxcCreateInstance"));
    auto createValidator=reinterpret_cast<DxcCreateInstanceProc>(GetProcAddress(validation,"DxcCreateInstance"));
    if (!create || !createValidator) throw std::runtime_error("SDK export missing");
    ComPtr<IDxcUtils> utils;
    checked(create(CLSID_DxcUtils,IID_PPV_ARGS(&utils)),"CreateUtils");
    ComPtr<IDxcBlobEncoding> source;
    UINT32 encoding=assemble ? DXC_CP_UTF8 : 0;
    checked(utils->LoadFile(argv[3],&encoding,&source),"LoadFile");
    ComPtr<IDxcBlob> object;
    if (assemble) {
        ComPtr<IDxcAssembler> assembler;
        checked(create(CLSID_DxcAssembler,IID_PPV_ARGS(&assembler)),"CreateAssembler");
        ComPtr<IDxcOperationResult> operation;
        checked(assembler->AssembleToContainer(source.Get(),&operation),"AssembleToContainer");
        object=result(operation.Get(),"assembly_status");
        // These original game shaders have no STAT part; discard assembler-added reflection.
        ComPtr<IDxcContainerBuilder> builder;
        checked(create(CLSID_DxcContainerBuilder,IID_PPV_ARGS(&builder)),"CreateContainerBuilder");
        checked(builder->Load(object.Get()),"LoadContainer");
        checked(builder->RemovePart(DXC_PART_REFLECTION_DATA),"RemoveAddedReflection");
        ComPtr<IDxcOperationResult> serialized;
        checked(builder->SerializeContainer(&serialized),"SerializeContainer");
        object=result(serialized.Get(),"container_status");
    } else checked(source.As(&object),"InputBlob");
    if (!object) throw std::runtime_error("assembler returned no object");
    ComPtr<IDxcValidator> validator;
    checked(createValidator(CLSID_DxcValidator,IID_PPV_ARGS(&validator)),"CreateExternalValidator");
    ComPtr<IDxcOperationResult> operation;
    checked(validator->Validate(object.Get(),DxcValidatorFlags_Default,&operation),"Validate");
    auto validated=result(operation.Get(),"validation_status");
    if (assemble) write_new(argv[4],validated.Get());
    printf("status=PASS assembled=%d input_bytes=%zu object_bytes=%zu validated_bytes=%zu\n",assemble,source->GetBufferSize(),object->GetBufferSize(),validated ? validated->GetBufferSize() : 0);
    return 0;
}
int wmain(int argc,wchar_t** argv) {
    bool assemble=argc>=2 && wcscmp(argv[1],L"assemble")==0;
    bool validate=argc>=2 && wcscmp(argv[1],L"validate")==0;
    if ((!assemble && !validate) || argc!=(assemble ? 5 : 4)) {
        fputs("dxil_roundtrip <assemble|validate> <absolute-SDK-dir> <input> [new-output]\n",stderr);
        return 2;
    }
    std::wstring sdk=argv[2];
    if (sdk.size()<3 || sdk[1]!=L':' || (sdk[2]!=L'\\' && sdk[2]!=L'/')) return 2;
    HMODULE compiler=LoadLibraryExW((sdk+L"\\dxcompiler.dll").c_str(),nullptr,LOAD_LIBRARY_SEARCH_DLL_LOAD_DIR|LOAD_LIBRARY_SEARCH_SYSTEM32);
    HMODULE validation=LoadLibraryExW((sdk+L"\\dxil.dll").c_str(),nullptr,LOAD_LIBRARY_SEARCH_DLL_LOAD_DIR|LOAD_LIBRARY_SEARCH_SYSTEM32);
    int code=1;
    try {
        if (!compiler || !validation) throw std::runtime_error("cannot load pinned SDK DLLs");
        code=work(assemble,compiler,validation,argv);
    } catch (const std::exception& error) { fprintf(stderr,"FAIL: %s\n",error.what()); }
    if (validation) FreeLibrary(validation);
    if (compiler) FreeLibrary(compiler);
    return code;
}
