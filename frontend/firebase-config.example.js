// Copy this file to firebase-config.js and fill it with your Firebase web app values.
// Enable Firebase Authentication -> Email/Password in the Firebase console.
// The app stays in local analyst mode until firebase-config.js exists.
//
// Role hierarchy:
// - Default signed-in users are viewers.
// - Add Firebase custom claims to make users analysts/admins:
//   { role: "analyst" } or { analyst: true }
//   { role: "admin" } or { admin: true }
window.PRISMEDGE_FIREBASE_CONFIG = {
  apiKey: "",
  authDomain: "",
  projectId: "",
  storageBucket: "",
  messagingSenderId: "",
  appId: ""
};
