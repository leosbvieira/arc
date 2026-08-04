const { AndroidConfig, withAndroidManifest } = require("@expo/config-plugins");

// The local BFF is served over HTTP on the private LAN until the VPS/HTTPS deploy.
module.exports = function withCleartextTraffic(config) {
  return withAndroidManifest(config, (androidConfig) => {
    const application = AndroidConfig.Manifest.getMainApplicationOrThrow(
      androidConfig.modResults,
    );
    application.$["android:usesCleartextTraffic"] = "true";
    return androidConfig;
  });
};
