# SICD metadata report

Generated: `2026-08-29T13:45:03.976411+00:00`

## Provenance and status

- Public asset: `https://umbra-open-data-catalog.s3.us-west-2.amazonaws.com/sar-data/task-data/f2f8c71e-6aec-4358-acda-93c5e68e8b4b/2025-02-16-18-55-44_UMBRA-10/2025-02-16-18-55-44_UMBRA-10_SICD.nitf`
- HTTP Content-Length: `11478596733` bytes.
- The full SICD is **not yet downloaded**. Metadata was extracted with byte-range requests for the NITF header, second image subheader, and SICD DES XML.
- NITF-declared file length: `11478596733` bytes; match with HTTP: `True`.
- SICD 1.3.0 XML schema validation: `True`.

The NITF contains two vertically joined image segments (11,595 + 1,715 rows) and one SICD XML DES. The joined dimensions agree with ImageData.

## ImageData

- NumRows: `13310`
- NumCols: `107800`
- PixelType: `RE32F_IM32F` (complex float32 real/imaginary)
- SCPPixel: row `6655`, col `53900`

## Grid

- Grid.Type / ImagePlane: `RGAZIM` / `SLANT`
- Row: SS `0.167993380972` m, ImpRespBW `4.76209238347` 1/m, DeltaK1/2 `-2.38104619173` / `2.38104619173` 1/m, Sgn `-1`.
- Col: SS `0.0564352651636` m, ImpRespBW `14.1755336434` 1/m, DeltaK1/2 `-7.08776682169` / `7.08776682169` 1/m, Sgn `-1`.
- Row/Col DeltaKCOAPoly: `[[0.0]]` / `[[0.0]]`.
- Both dimensions declare `SVA` weighting; explicit WgtFunct samples are absent.
- Processed support occupies `0.8` of the Col FFT, about `86240` of `107800` bins.

## Timeline and ImageFormation

- CollectStart: `2025-02-16T18:55:33.000000Z`
- Timeline.CollectDuration: `22.5479404467` s
- ImageFormAlgo: `PFA`
- TStartProc / TEndProc: `0.00516153517446` / `18.0732232564` s
- **Processed aperture duration: `18.0680617212` s.**
- Processed frequency range: `9372871761.44` to `10086691451.9` Hz
- Processing polarization: `V:V`

The processed duration, not Timeline.CollectDuration, is the available aperture baseline for SICD sub-aperture splitting. Consequently a 20 s sub-aperture cannot be produced from this SICD.

## SCPCOA and geolocation

- SCPTime: `9.0363612956` s
- Slant / ground range: `610403.751069` / `208153.045445` m
- Graze / incidence: `68.1570747671` / `21.8429252329` deg
- AzimAng: `101.919310567` deg; SideOfTrack `R`; DopplerConeAng `90.1637144264` deg
- SCP LLH: `34.581401673389436`, `-120.62709868658314`, HAE `101.524756674` m
- Derived platform ground-track bearing at SCPTime: `191.185802655` deg
- Col ground-projection bearing: `191.246710754` deg

## Range/azimuth axis determination

- Grid.Type is `RGAZIM`. In SICD/SarPy the coordinate order is Row then Col; RGAZIM means range then Doppler/azimuth.
- Range = Row = NumPy `axis=0`.
- Azimuth/Doppler = Col = NumPy `axis=1`.
- Col.Sgn is `-1`; image-to-spectrum must use `sarpy.processing.sicd.fft_base.fft_sicd(array, 1, sicd)`, which is `numpy.fft.fft(axis=1)` for this file.
- Col DeltaKCOAPoly is zero: `True`; no Col deskew phase is required for this product.

This conclusion is unambiguous for this SICD. A generic splitter must still reject other Grid.Type values unless explicitly validated.

## CPHD comparison

- Same collect UUID: `True`; same CollectionStart: `True`.
- CPHD dwell: `22.5408125134` s; SICD Timeline duration: `22.5479404467` s; SICD processed duration: `18.0680617212` s.
- SICD processed duration is `80.1571004174`% of the CPHD dwell.
- SCP/reference time offset (SICD minus CPHD): `-2.03888836768` s.
- Azimuth/incidence differences: `-3.92904515417` / `-0.0656147094159` deg.

The geometry differences are explained by the different reference times; they are not evidence that the products belong to different collects.

## Validation caveats

- The XML is XSD-valid.
- SarPy 2.0.1 recursive semantic validation returns false because SVA lacks WgtFunct and because its waveform validator assumes a positive chirp rate. The negative-rate chirp is internally consistent when bandwidth is checked with `abs(TxFMRate)`: the derived endpoints exactly match RadarCollection.TxFrequency.
- Missing SVA samples are scientifically relevant: native spectral deweighting cannot be reconstructed exactly from this metadata. Initial tests must preserve the native weighting and clearly describe any additional window.
