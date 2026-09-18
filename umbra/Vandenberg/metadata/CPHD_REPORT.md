# CPHD metadata report

Generated: `2026-08-29T13:45:00.531538+00:00`

## Scope and integrity

- Source: `D:\Dati Tesi\Umbra\Vandenberg\2025-02-16-18-55-44_UMBRA-10_CPHD.cphd`
- File size: `140554224768` bytes; expected-size match: `True`.
- Format: `CPHD/1.1.0`; XML size: `20373` bytes.
- Signal block ends exactly at EOF: `True`.
- Signal size matches NumVectors x NumSamples x sample bytes: `True`.
- Access performed: ASCII header, XML, and memory-mapped PVP only. **The signal block was not read.**

SarPy recursive semantic validation: `True`.

## Collection and channel

- Collector/platform: `Umbra-10`; core name: `2025-02-16-18-55-33_Umbra-10`.
- Collect UUID: `9d8283d8-550d-4435-899f-5483d2c1abcc`.
- Type/mode/domain: `MONOSTATIC` / `SPOTLIGHT` / `FX`.
- CollectionStart: `2025-02-16T18:55:33.000000Z`.
- Channels: `1` (`Primary`); format `CF8`.
- NumVectors: `165924`; NumSamples: `105840`; PVP bytes/vector: `376`.
- Polarization: `V:V`.
- Center frequency: `9799978362.63` Hz; bandwidth: `854213202.372` Hz.

## Timing and pulse cadence

- XML TxTime1 / TxTime2: `0.00297987466667` / `22.5437761093` s.
- XML TxTime span: `22.5407962347` s.
- DwellTimePoly constant: `22.5408125134` s; SRPDwellTime: `22.5408125134` s.
- PVP first / last TxTime: `0.00297987466667` / `22.5437761093` s; span `22.5407962347` s.
- TxTime strictly monotonic: `True`.
- Nominal local pulse rate from median per-pulse interval: `7470.71479801` Hz.
- Mean rate of stored PVP vectors over the span: `7361.00882474` vectors/s.
- PulseNumber range: `53` to `168257`; missing numbers in the contiguous span: `2281`.

The two rates differ because the PVP sequence contains pulse-number gaps. Therefore no single constant PRF is hardcoded.

## Reference geometry

- SRP/IARP LLH: `34.581401673389436`, `-120.62709868658314`, HAE `101.524756674` m.
- SideOfTrack: `R`.
- Slant / ground range: `610631.063332` / `208717.304577` m.
- Graze / incidence: `68.0914600576` / `21.9085399424` deg.
- Viewing azimuth: `105.848355722` deg clockwise from true north.
- Doppler cone angle: `91.5045319687` deg.
- Derived ground-track azimuth: `191.199523702` deg; undirected azimuth axis `11.1995237021` deg.

The derived 191.20 deg ground track and 11.20 deg undirected axis confirm the preliminary geometry; they are derived values, not hardcoded assumptions.

## PVP fields

| Field | Offset (8-byte words) | Size (words) | Format |
|---|---:|---:|---|
| TxTime | 0 | 1 | `F8` |
| TxPos | 1 | 3 | `X=F8;Y=F8;Z=F8;` |
| TxVel | 4 | 3 | `X=F8;Y=F8;Z=F8;` |
| RcvTime | 15 | 1 | `F8` |
| RcvPos | 16 | 3 | `X=F8;Y=F8;Z=F8;` |
| RcvVel | 19 | 3 | `X=F8;Y=F8;Z=F8;` |
| SRPPos | 30 | 3 | `X=F8;Y=F8;Z=F8;` |
| aFDOP | 33 | 1 | `F8` |
| aFRR1 | 34 | 1 | `F8` |
| aFRR2 | 35 | 1 | `F8` |
| FX1 | 36 | 1 | `F8` |
| FX2 | 37 | 1 | `F8` |
| TOA1 | 38 | 1 | `F8` |
| TOA2 | 39 | 1 | `F8` |
| TOAE1 | 40 | 1 | `F8` |
| TOAE2 | 41 | 1 | `F8` |
| TDTropoSRP | 42 | 1 | `F8` |
| SC0 | 43 | 1 | `F8` |
| SCSS | 44 | 1 | `F8` |
| SIGNAL | 45 | 1 | `I8` |
| TxACX | 7 | 3 | `X=F8;Y=F8;Z=F8;` |
| TxACY | 10 | 3 | `X=F8;Y=F8;Z=F8;` |
| TxEB | 13 | 2 | `DCX=F8;DCY=F8;` |
| RcvACX | 22 | 3 | `X=F8;Y=F8;Z=F8;` |
| RcvACY | 25 | 3 | `X=F8;Y=F8;Z=F8;` |
| RcvEB | 28 | 2 | `DCX=F8;DCY=F8;` |
| PulseNumber | 46 | 1 | `U8` |

## Interpretation

- Measured CPHD dwell is about 22.5408 s, consistent with but more precise than the preliminary ~22.6 s.
- The CPHD is the authoritative source for the later slow-time/look-angle/Doppler mapping.
- The XML reports a fixed SRP and FX-domain data; no signal samples were inspected at this checkpoint.
