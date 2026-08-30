# RC4 UI/setup hardware acceptance checkpoint

Date: 2026-08-30

This checkpoint records mature-appliance acceptance of the RC4 presentation/setup/UI batch before TGIF Control Center work begins.

Accepted implementation head before this checkpoint:

`f294e7941bd96caf3b55e1597a934a1b0527c5eb`

Hardware/browser acceptance:

- integrated BrandMeister + TGIF appliance/login/update presentation works as expected;
- normal `.ywdsettings` confirm-import preview shows redacted TGIF enabled/master/port/password-configured state;
- revised Digital Waterfall loading animation looks correct and works as expected;
- Digital Waterfall is the fresh/default loading animation while an existing saved theme remains preserved;
- existing BrandMeister + TGIF runtime, RF stack, plugins, SSH, OLED and dashboard behavior remained healthy during the update and validation;
- expanded RC4 source/regression gate passed;
- zero new operational regression was reported.

Deferred final image gate:

- the HTTP-only first-run setup listener and manual TGIF first-run entry are source-regression covered but cannot be meaningfully exercised on an already-provisioned appliance;
- they remain scheduled for physical acceptance on the actual RC4 factory image before publication.

Branch policy at this checkpoint:

- `dev` is the canonical implementation line;
- `dev-plugins` is fast-forward aligned to the accepted implementation before new TGIF Control Center work;
- `main` remains the public RC3 known-good line;
- `VERSION` remains `0.2.0-rc3` until RC4 freeze.

The next slice may improve TGIF dashboard/control ergonomics, but must not casually change the already-proven BrandMeister/TGIF DMRGateway routing rules.
