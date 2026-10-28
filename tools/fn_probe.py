import pandas as pd
f="research/fortnite_DX12_PerformanceMode/pmcap-FortniteClient-Win64-Shipping.exe-260903-212226.csv"
d=pd.read_csv(f,low_memory=False)
print("swapchains:"); print(d.groupby("SwapChainAddress").agg(n=("TimeInSeconds","size"),t0=("TimeInSeconds","min"),t1=("TimeInSeconds","max")))
print("\nFrameType:"); print(d.FrameType.value_counts(dropna=False))
print("\nPresentMode:"); print(d.PresentMode.value_counts(dropna=False))
print("\nPresentRuntime:"); print(d.PresentRuntime.value_counts(dropna=False))
print("\nProcessID:"); print(d.ProcessID.value_counts(dropna=False))
print("\nApplication:"); print(d.Application.value_counts(dropna=False))
print("\nhead 15 (sel cols):")
print(d[["SwapChainAddress","FrameType","TimeInSeconds","MsBetweenPresents","MsBetweenDisplayChange","MsBetweenSimulationStart","MsGPUBusy","MsCPUBusy"]].head(15).to_string())
