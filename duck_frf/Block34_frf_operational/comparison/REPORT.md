# October 2021: three-event observational comparison

Catalogue footprints/timestamps only; no SAR valid support, phase, inversion or scene choice. ROI not supplied. Eligibility is implemented QC/time only, NOT physical representativity.

## Published versus native discrete spectral peak

| acquisition | instrument | UTC spectrum | QC E | Tp published s | Tp bin s | Hm0 derived m | sigma frequency Hz | numerical local maxima |
|---|---|---|---:|---:|---:|---:|---:|---|
|TSX-1_record_12|FRF:waverider-17m|2021-10-12T11:00:00.000003+00:00|1.0|9.191176|9.30232558139535|1.457074952842166|0.07963428253397281|[(0.1075, 1.4620563), (0.13, 1.1604674), (0.0775, 1.0107902), (0.19, 0.524086), (0.16, 0.46224236)]|
|TSX-1_record_12|FRF:8m-array|2021-10-12T11:00:00.000003+00:00|1.0|8.596374|8.695652173913043|1.294043852494961|0.0625858885356867|[(0.115, 1.0809385), (0.175, 0.32911286), (0.1975, 0.28308725), (0.25, 0.20667797)]|
|TSX-1_record_12|FRF:waverider-26m|2021-10-12T11:29:59.999997+00:00|1.0|11.080333|8.16326530612245|1.881601714667586|0.08756617641172183|[(0.1225, 1.7482553), (0.1, 1.7033626), (0.07, 1.0884773), (0.22, 0.85884255), (0.1825, 0.66704565)]|
|TSX-1_record_12|FRF:awac-11m|2021-10-12T11:00:00.500001+00:00|1.0|8.639309|8.695652173913043|1.3463657900956931|0.07723581005769231|[(0.115, 1.1743801), (0.1375, 0.8813652), (0.1825, 0.37298986), (0.22, 0.34256253), (0.25, 0.26940885)]|
|COSMO_2098202|FRF:waverider-17m|2021-10-13T23:00:00.000003+00:00|1.0|9.546539|9.30232558139535|1.108154483705228|0.0902500002663913|[(0.1075, 0.69379526), (0.1375, 0.6095841), (0.1975, 0.27664724), (0.235, 0.19796228), (0.0625, 0.08224731)]|
|COSMO_2098202|FRF:8m-array|2021-10-13T23:00:00.000003+00:00|1.0|10.578512|10.81081081081081|1.0385377495960366|0.05937236458387512|[(0.0925, 0.8330175), (0.1525, 0.33391467), (0.1675, 0.30768907), (0.265, 0.08788637)]|
|COSMO_2098202|FRF:waverider-26m|2021-10-13T23:00:00.000003+00:00|1.0|10.810811|10.81081081081081|1.3018658614311998|0.08794774260201807|[(0.0925, 1.5508119), (0.13, 0.81669897), (0.115, 0.75553656), (0.1675, 0.45867863), (0.25, 0.18917361)]|
|COSMO_2098202|FRF:awac-11m|2021-10-13T23:00:00.500001+00:00|1.0|8.316009|8.16326530612245|1.1006101719137433|0.0938447163921924|[(0.1225, 0.78865486), (0.1375, 0.50794274), (0.1, 0.472106), (0.1675, 0.44894657), (0.19, 0.30659905)]|
|TDX-1_record_11|FRF:waverider-17m|2021-10-13T23:00:00.000003+00:00|1.0|9.546539|9.30232558139535|1.108154483705228|0.0902500002663913|[(0.1075, 0.69379526), (0.1375, 0.6095841), (0.1975, 0.27664724), (0.235, 0.19796228), (0.0625, 0.08224731)]|
|TDX-1_record_11|FRF:8m-array|2021-10-13T23:00:00.000003+00:00|1.0|10.578512|10.81081081081081|1.0385377495960366|0.05937236458387512|[(0.0925, 0.8330175), (0.1525, 0.33391467), (0.1675, 0.30768907), (0.265, 0.08788637)]|
|TDX-1_record_11|FRF:waverider-26m|2021-10-13T23:00:00.000003+00:00|1.0|10.810811|10.81081081081081|1.3018658614311998|0.08794774260201807|[(0.0925, 1.5508119), (0.13, 0.81669897), (0.115, 0.75553656), (0.1675, 0.45867863), (0.25, 0.18917361)]|
|TDX-1_record_11|FRF:awac-11m|2021-10-13T23:00:00.500001+00:00|1.0|8.316009|8.16326530612245|1.1006101719137433|0.0938447163921924|[(0.1225, 0.78865486), (0.1375, 0.50794274), (0.1, 0.472106), (0.1675, 0.44894657), (0.19, 0.30659905)]|

## Interpretation limits

Published Tp can use a supplier parabolic fit while the diagnostic uses the maximum native bin. The two definitions are not interchangeable; the metadata definition is retained in SPECTRAL_DIAGNOSTICS.json. Native bin steps and half-peak contiguous widths quantify sampling/broadness, not extra resolution from plotting. Numerical adjacent maxima do NOT prove multiple independent wave systems.

Waverider ~9.55 s versus AWAC ~8.32 s is evaluated using their own spectra, QC, original nominal position/depth and time. Even the discrete-bin periods differ (~9.30 versus ~8.16 s); supplier peak fitting alone does not remove the difference. Direction mean/mode/spread at the published peak frequency are preserved separately in EVENT_PARAMETERS.csv and diagnostics, not replaced by whole-spectrum mean.

No automatic explanation by refraction, current, instrument bias or distinct systems. Nominal depths/positions and unverified burst anchors constrain interpretation; the recovered context does not bridge the long gap between TSX and later events. No sensor/current or wind-height conversion.

Shared parameter references: 36 entries in COMMON_RECORDS.json; COSMO/TDX references can be identical and are never counted as separate spectra in the overlay.

Wind height/elevation and averaging hints, current components/depth bins and tide datum remain original in EVENT_PARAMETERS.csv and per-event TENSORS/REPORT. Missing/technical/unsupported states and survey references remain in each dossier; no full surveyed seabed coverage is inferred.

Figures: map, unique spectra overlay and context series use supplier QC distinctions; context uses scatter to avoid connecting gaps.
