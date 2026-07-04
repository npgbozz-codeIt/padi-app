# src/utils/responses.py

ONBOARDING_RESPONSES = {
    "english": {
        "ask_lang": "Welcome to MyPadi! 🇳🇬 Please reply with your preferred language: 'english', 'pidgin', or 'hausa'.",
        "invalid_lang": "Invalid selection. Please type 'english', 'pidgin', or 'hausa'.",
        "ask_phone": "Language saved! Please click the button below to share your phone number securely.",
        "ask_bvn": "Phone number recorded. Kindly type out your 11-digit BVN to continue security verification.",
        "invalid_bvn": "Invalid BVN. Your Bank Verification Number must be exactly 11 numeric digits. Try again:",
        "ask_pin": "BVN accepted! 🔐 Now, enter a secure 4-digit transaction PIN to protect your wallet:",
        "invalid_pin": "Security alert: Your PIN must be exactly 4 digits long. Try again:",
        "confirm_pin": "Please re-type your 4-digit PIN to confirm it:",
        "mismatch_pin": "PINs do not match! Let's restart: Enter a new 4-digit PIN:",
        "completed": "Onboarding complete! 🥳 Welcome to MyPadi. Your account tag is active. What bills are we paying today?",
    },
    "pidgin": {
        "ask_lang": "Welcome to MyPadi! 🇳🇬 Abeg reply with the language wey you prefer: 'english', 'pidgin', or 'hausa'.",
        "invalid_lang": "That choice no follow. Abeg type 'english', 'pidgin', or 'hausa'.",
        "ask_phone": "Language saved sharp-sharp! Abeg click the button below to share your phone number make we link your account.",
        "ask_bvn": "Phone number done land! Now, abeg type your 11-digit BVN make we confirm your secure profile.",
        "invalid_bvn": "This BVN no correct. Your BVN suppose be exactly 11 numbers. Type am again:",
        "ask_pin": "BVN confirmed! 🔐 Now, type the 4-digit PIN wey you wan dey use run transactions:",
        "invalid_pin": "Your PIN must be exactly 4 numbers. Type am again:",
        "confirm_pin": "Abeg enter that same PIN again make we confirm am:",
        "mismatch_pin": "The two PINs no match at all! Make we start again: Type a fresh 4-digit PIN:",
        "completed": "Onboarding finish! 🥳 Welcome to MyPadi, your account done setup live. Which bills we dey pay today?",
    },
    "hausa": {
        "ask_lang": "Barka da zuwa MyPadi! 🇳🇬 Da fatan za ku zaɓi yaren da kuka fi so: 'english', 'pidgin', ko 'hausa'.",
        "invalid_lang": "Zaɓin da ba daidai ba. Da fatan za ku rubuta 'english', 'pidgin', ko 'hausa'.",
        "ask_phone": "An adana yarenku! Tura lambar wayarku don Allah ta danna maballin da ke ƙasa.",
        "ask_bvn": "An yi nasarar adana lambar wayarku. Don Allah saka lambar BVN dinku guda 11.",
        "invalid_bvn": "Lambar BVN ba daidai ba ce. Dole ne ya zama lambobi 11 daidai. Sake gwadawa:",
        "ask_pin": "An karɓi BVN! 🔐 Yanzu, saka lambar sirri guda 4 don kiyaye asusunku:",
        "invalid_pin": "Dole ne lambar sirri ta zama lambobi 4 daidai. Sake gwadawa:",
        "confirm_pin": "Da fatan za ku sake saka lambar sirrin asusunku guda 4 don tabbatarwa:",
        "mismatch_pin": "Lambar sirri ba ta yi daidai ba! Bari mu sake farawa: Saka sabuwar lambar sirri guda 4:",
        "completed": "An kammala rajista! 🥳 Barka da zuwa MyPadi. Wace lissafin kuke son biya yau?",
    },
}


TRANSACTION_RESPONSES = {
    "english": {
        "missing_slots": "❌ Details incomplete. Please specify the provider, amount, and phone number clearly.",
        "insufficient_funds": "❌ Transaction failed. Insufficient funds. Your current wallet balance is ₦{balance}.",
        "vending_success": "🎉 Success! ₦{amount} {provider} airtime has been sent to {recipient}.",
        "vending_failed": "❌ Failed: {error}"
    },
    "pidgin": {
        "missing_slots": "❌ Dis details no complete. Abeg tell me the network, how much, and phone number well.",
        "insufficient_funds": "❌ Your money no reach. Your wallet balance na ₦{balance}.",
        "vending_success": "🎉 E don go! We don send ₦{amount} {provider} airtime to {recipient}.",
        "vending_failed": "❌ Error happen: {error}"
    },
    "hausa": {
        "missing_slots": "❌ Cikakken bayani bai cika ba. Da fatan za a fadi hanyar sadarwa, adadin kudi, da lambar waya.",
        "insufficient_funds": "❌ Kudinka bai isa ba. Ma'ajin ku shine ₦{balance}.",
        "vending_success": "🎉 An yi nasara! An tura ₦{amount} {provider} zuwa {recipient}.",
        "vending_failed": "❌ Kuskure: {error}"
    }
}
