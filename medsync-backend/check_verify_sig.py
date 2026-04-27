from webauthn import verify_registration_response
import inspect

sig = inspect.signature(verify_registration_response)
print("Parameters:")
for name, param in sig.parameters.items():
    print(f"  {name}: {param.annotation}")
