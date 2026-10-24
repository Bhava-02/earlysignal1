// Google sign-in and SMS codes through Firebase Authentication, in the browser. Active only when the server (or a
// static earlysignal-config.json) supplies the Firebase web settings. Firebase is used only to prove who someone is:
// the Google email or the phone number is checked against the EarlySignal account, then Firebase is signed out.
import { config } from './server'

let state = null

export const firebaseReady = () => !!config().firebase?.apiKey

async function load() {
  if (state) return state
  const [{ initializeApp }, mod] = await Promise.all([import('firebase/app'), import('firebase/auth')])
  const app = initializeApp(config().firebase)
  const auth = mod.getAuth(app)
  auth.useDeviceLanguage()
  if (config().firebase.emulator) mod.connectAuthEmulator(auth, config().firebase.emulator, { disableWarnings: true }) // local testing only
  state = { auth, mod }
  return state
}

const MESSAGES = {
  'auth/popup-closed-by-user': 'The Google window was closed before sign-in finished.',
  'auth/cancelled-popup-request': 'The Google window was closed before sign-in finished.',
  'auth/popup-blocked': 'The browser blocked the Google window. Allow pop-ups for this site and try again.',
  'auth/unauthorized-domain': "This web address is not on the Firebase project's list of authorised domains (Authentication, Settings, Authorized domains).",
  'auth/operation-not-allowed': 'This sign-in method is turned off in the Firebase project.',
  'auth/network-request-failed': 'Could not reach Google. Check the internet connection and try again.',
  'auth/invalid-phone-number': 'The phone number on this account is not a valid mobile number.',
  'auth/too-many-requests': 'Too many attempts from this device. Wait a few minutes and try again.',
  'auth/quota-exceeded': "Today's SMS limit for this project has been reached. Use the email option.",
  'auth/billing-not-enabled': 'SMS codes need the Firebase pay-as-you-go (Blaze) plan. Use the email option.',
  'auth/invalid-verification-code': 'That code is not correct.',
  'auth/code-expired': 'This code has expired. Send a new code.',
  'auth/captcha-check-failed': 'The security check failed. Reload the page and try again.',
  'auth/invalid-api-key': 'The Firebase settings on this server are not correct.',
  'auth/api-key-not-valid.-please-pass-a-valid-api-key.': 'The Firebase settings on this server are not correct.',
  'auth/missing-phone-number': 'This account has no phone number.',
  'auth/internal-error': "Could not reach Google's sign-in service. Check the internet connection, and that the Firebase settings on the server are correct.",
}
export const firebaseMessage = (e) => MESSAGES[e?.code] || (e?.message ? e.message.replace(/^Firebase:\s*/, '') : 'Something went wrong. Try again.')

// Opens Google's sign-in window. Returns the Google account's email and name (the email is checked by Google).
export async function googleSignIn() {
  const { auth, mod } = await load()
  const provider = new mod.GoogleAuthProvider()
  provider.setCustomParameters({ prompt: 'select_account' })
  const res = await mod.signInWithPopup(auth, provider)
  const out = { email: res.user.email || '', name: res.user.displayName || '', verified: !!res.user.emailVerified }
  await mod.signOut(auth).catch(() => {})
  return out
}

let verifier = null
// Sends a code by SMS. containerId: an empty element for the invisible security check. Returns a handle for confirmSms.
export async function sendSms(phoneE164, containerId) {
  const { auth, mod } = await load()
  if (verifier) {
    try { verifier.clear() } catch { /* already cleared */ }
    verifier = null
  }
  const box = document.getElementById(containerId)
  if (box) box.innerHTML = ''
  verifier = new mod.RecaptchaVerifier(auth, containerId, { size: 'invisible' })
  return mod.signInWithPhoneNumber(auth, phoneE164, verifier)
}

// Checks the SMS code. Returns the verified phone number; throws with a Firebase error code when it is wrong.
export async function confirmSms(handle, code) {
  const { auth, mod } = await load()
  const cred = await handle.confirm(code)
  const phone = cred.user.phoneNumber || ''
  await mod.signOut(auth).catch(() => {})
  return phone
}
