# Range-axis reconciliation

`105.848355722°` is **not** the SICD `SCPCOA.AzimAng`. It is the CPHD
`ReferenceGeometry.Monostatic.AzimuthAngle` at `11.075249663 s`.
The actual SICD value is `SCPCOA.AzimAng=101.919310567°` at
`SCPTime=9.036361296 s`. Direct interpolation of CPHD PVP positions reproduces
both values; the difference is the changing look azimuth over about 2.04 s.

At SICD SCP time, `AzimAng` is the directed ground-to-platform bearing. The
groundward slant LOS is `281.919310559°`.
Positive SICD Grid Row projected onto the SCP tangent plane is
`281.919311354°`. Thus LOS/Grid Row and `AzimAng` differ by 180° as
directed vectors but define the same undirected range axis (`101.919° mod 180`).

For a spatial spectrum, the appropriate comparison uses the local surface
Jacobian of the SICD Grid at the ROI, because it converts image frequencies to
east/north ground frequencies. Its positive Row bearing is
`281.178627303°` nearshore and
`281.188982031°` offshore. Surface projection
and displacement from the SCP account for their small offsets from the tangent
Grid Row.

| ROI | wavevector | local surface Row | difference | difference from SICD SCPCOA axis | difference from CPHD-reference axis |
|---|---:|---:|---:|---:|---:|
| nearshore | 79.836° | 281.179° | 21.343° | 22.084° | 26.013° |
| offshore | 115.829° | 281.189° | 14.640° | 13.910° | 9.981° |

Therefore the Block-3 values `21.3°` and `14.6°` are internally consistent and
refer specifically to the **local surface projection of Grid Row**.
