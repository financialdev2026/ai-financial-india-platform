/*
  Creates or updates the PrismEdge owner account and assigns Firebase custom claims.

  Requirements:
  1. Install firebase-admin in the project root:
     npm install firebase-admin
  2. Download a Firebase service account JSON from:
     Firebase Console -> Project Settings -> Service accounts -> Generate new private key
  3. Run:
     $env:GOOGLE_APPLICATION_CREDENTIALS="C:\path\to\serviceAccount.json"
     $env:PRISMEDGE_ADMIN_EMAIL="udaylowalekar@gmail.com"
     $env:PRISMEDGE_ADMIN_PASSWORD="<your-password>"
     node firebase_admin_setup.js

  Do not commit service account JSON files or plaintext passwords.
*/

const admin = require("firebase-admin");

const email = process.env.PRISMEDGE_ADMIN_EMAIL || "udaylowalekar@gmail.com";
const password = process.env.PRISMEDGE_ADMIN_PASSWORD;

if (!password) {
  console.error("Missing PRISMEDGE_ADMIN_PASSWORD environment variable.");
  process.exit(1);
}

admin.initializeApp({
  credential: admin.credential.applicationDefault()
});

async function main() {
  let user;
  try {
    user = await admin.auth().getUserByEmail(email);
    await admin.auth().updateUser(user.uid, {
      password,
      emailVerified: true,
      disabled: false
    });
  } catch (error) {
    if (error.code !== "auth/user-not-found") throw error;
    user = await admin.auth().createUser({
      email,
      password,
      emailVerified: true,
      disabled: false
    });
  }

  await admin.auth().setCustomUserClaims(user.uid, {
    role: "admin",
    admin: true,
    analyst: true
  });

  console.log(`Admin role assigned to ${email}.`);
  console.log("Sign out and sign in again so the browser receives the updated token.");
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
