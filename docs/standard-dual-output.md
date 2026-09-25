# Standard mode: two outputs on either platform

The application generates both files on macOS **and** Windows:

- `name.icc`: calibrated display description for macOS ColorSync / conventional ICC workflows.
- `name-mhc2.icc`: Windows MHC2 output.

The host platform selects the bundled MHC2Gen executable only. It does not select which output is generated. Both files are built before publishing, and an existing file is never overwritten.

## Input and settings

Select a matrix/TRC Display ICC matching the display's **current hardware mode**. Standard mode does not require measurement data, a CUBE, or a SpaceMan profile. It cannot compensate for differences between the assumed standard display and the actual hardware.

White point and gamma apply to both outputs. The regular profile uses VCGT to calibrate the channels and describes the display after that calibration. Its RGB colorants retain the real display primaries, rather than claiming that a wide-gamut display has become sRGB. ColorSync handles content-to-display conversion in color-managed applications; this is not a universal gamut clamp for unmanaged content.

Target Gamut controls the Windows MHC2 transform. The regular profile does not implement that gamut clamp. No interface size, layout or palette changes were made; the Target Gamut tooltip explains this distinction.

Changing white point can reduce maximum luminance. The regular profile updates luminance only when the source contains it; it does not invent an absolute luminance measurement.

## Validation

- The Adobe RGB → D50 regular profile reproduces the user-verified v6mac colorants, TRCs, white-point/adaptation tags and VCGT exactly when gamma is 2.19921875 (the Adobe RGB source value).
- Selecting Gamma 2.2 intentionally requests 2.2, rather than silently substituting 2.19921875.
- Existing MHC2 reference transforms remain regression-tested.
- Automated tests cover both Generate workflows, file collision protection, pair-generation failures, D65/D50/custom white, gamma and sRGB curves, Unicode names, and preserved display primaries.
- macOS-native ColorSync checks cover profile verification, display names, and VCGT transfer-table extraction. VCGT uses the verified 256-entry format; 4096-entry VCGT failed native extraction on the test machine and is not used.
- New packaged Windows/macOS applications have not been built as part of this change. Windows execution and physical display accuracy beyond the already verified reference remain subject to testing on the target system.

Run the development UI with `python preview_v110.py`; run tests with `QT_QPA_PLATFORM=offscreen python -m unittest discover -s tests -v`.
