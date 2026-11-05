// PiFire grills are reached over plain HTTP on the local network
// (e.g. http://pifire.local or http://192.168.1.50). Android 9+ blocks
// cleartext HTTP by default, and Expo's prebuild only re-enables it in the
// debug manifests -- so a release APK (what the GitHub workflow builds) could
// never reach the smoker: every fetch and the socket.io connection failed
// before leaving the phone. This plugin turns cleartext back on in the main
// manifest so release builds behave like debug builds.
const { withAndroidManifest } = require("expo/config-plugins");

module.exports = function withCleartextTraffic(config) {
  return withAndroidManifest(config, (cfg) => {
    const app = cfg.modResults.manifest.application?.[0];
    if (app) {
      app.$["android:usesCleartextTraffic"] = "true";
    }
    return cfg;
  });
};
