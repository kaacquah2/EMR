import pyotp
import time

secret = "WH3LLY7YJQDER2CXPNQ4ZNIRCUST4C7Y"
totp = pyotp.TOTP(secret)

print(f"Current TOTP code: {totp.now()}")
print(f"Time remaining: {30 - (int(time.time()) % 30)} seconds")
print(f"\nCodes valid in next 2 minutes:")
for i in range(4):
    print(f"  +{i*30}s: {totp.at(time.time() + i*30)}")
