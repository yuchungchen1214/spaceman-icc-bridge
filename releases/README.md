# Release archive

Platform release versions are tracked independently. Keep each published
artifact under its versioned platform directory; do not build over or replace
archived files when preparing a later release.

| Platform | Version | Archive | Status |
| --- | --- | --- | --- |
| macOS arm64 | 1.2.0 | [`1.2.0/macos/`](1.2.0/macos/) | DMG built; packaged UI, synthetic ICC generation, and disk-image integrity verified; not yet hardware-validated |
| Windows x64 | 1.2.0 | [`1.2.0/windows/`](1.2.0/windows/) | Restored-UI single-file EXE archived; startup confirmed and 9 automated tests passed (1 macOS-only test skipped). ICC generation was not re-run on this exact restored-UI binary. |
| macOS arm64 | 1.1.0 | [`1.1.0/macos/`](1.1.0/macos/) | DMG archived; SHA256 and disk-image integrity verified |
| Windows x64 | 1.1.0 | [`1.1.0/windows/`](1.1.0/windows/) | Single-file EXE archived; user confirmed successful launch and generation test |
| macOS arm64 | 1.0.2 | [`1.0.2/macos/`](1.0.2/macos/) | DMG archived; bundled MHC2Gen tested with synthetic ICC data |
| Windows x64 | 1.0.1 | [`1.0.1/windows/`](1.0.1/windows/) | Single-file EXE and handoff package archived; see platform README for validation status |

Version numbers are archived independently by platform. Keep older artifacts
for reference; do not replace them when preparing a later release.
