# State Machines - Quick Reference Guide

## Module Location
```
medsync-backend/api/state_machines.py
```

## Import Usage

### Referral Validation
```python
from api.state_machines import validate_referral_transition, StateMachineError

try:
    validate_referral_transition(current_status, new_status)
except StateMachineError as e:
    return Response({"message": str(e)}, status=400)
```

### Lab Order Validation
```python
from api.state_machines import validate_lab_order_transition, StateMachineError

try:
    validate_lab_order_transition(current_status, new_status)
except StateMachineError as e:
    return Response({"message": str(e)}, status=400)
```

### Visit Status Validation
```python
from api.state_machines import validate_visit_status_transition, StateMachineError

try:
    validate_visit_status_transition(current_status, new_status)
except StateMachineError as e:
    return Response({"message": str(e)}, status=400)
```

---

## Valid Transitions

### Referral
| From | To |
|------|-----|
| PENDING | ACCEPTED |
| PENDING | REJECTED |
| ACCEPTED | COMPLETED |
| ACCEPTED | CANCELLED |

### Lab Order
| From | To |
|------|-----|
| ordered | collected |
| ordered | cancelled |
| collected | in_progress |
| collected | cancelled |
| in_progress | resulted |
| in_progress | cancelled |
| resulted | verified |

### Visit Status
| From | To |
|------|-----|
| registered | waiting_triage |
| registered | waiting_doctor |
| registered | discharged |
| waiting_triage | waiting_doctor |
| waiting_triage | sent_to_lab |
| waiting_triage | admitted |
| waiting_triage | discharged |
| waiting_doctor | in_consultation |
| waiting_doctor | sent_to_lab |
| waiting_doctor | admitted |
| waiting_doctor | discharged |
| in_consultation | sent_to_lab |
| in_consultation | admitted |
| in_consultation | discharged |
| sent_to_lab | in_consultation |
| sent_to_lab | waiting_doctor |
| sent_to_lab | waiting_triage |
| sent_to_lab | discharged |
| admitted | discharged |

---

## Error Message Format

Invalid transitions return HTTP 400 with a message indicating:
1. Current state
2. Requested state
3. Allowed transitions from current state

**Example:**
```
Invalid referral status transition: 'PENDING' → 'COMPLETED'. 
Allowed transitions from 'PENDING': ['ACCEPTED', 'REJECTED']
```

---

## Files Using State Machines

1. **medsync-backend/api/views/referral_views.py**
   - Function: `referral_update()`
   - Line: 167

2. **medsync-backend/api/views/lab_views.py**
   - Function: `lab_order_detail()` - Line 303
   - Function: `lab_order_result()` - Line 351

3. **medsync-backend/api/views/encounter_views.py**
   - Function: `encounter_detail()` - Line 330
   - Function: `close_encounter()` - Line 402

---

## Adding a New State Machine

1. **Define transitions in state_machines.py:**
```python
NEW_ENTITY_TRANSITIONS = {
    'state_a': ['state_b', 'state_c'],
    'state_b': ['state_d'],
    'state_c': ['state_d'],
    'state_d': [],  # Terminal state
}
```

2. **Add validation function:**
```python
def validate_new_entity_transition(current: str, new: str) -> None:
    validate_transition(current, new, NEW_ENTITY_TRANSITIONS, "new entity")
```

3. **Use in views:**
```python
from api.state_machines import validate_new_entity_transition, StateMachineError

try:
    validate_new_entity_transition(old_status, new_status)
except StateMachineError as e:
    return Response({"message": str(e)}, status=400)

# Update status after validation passes
entity.status = new_status
entity.save()
```

---

## Testing State Machines

```python
from api.state_machines import (
    validate_referral_transition,
    validate_lab_order_transition,
    validate_visit_status_transition,
    StateMachineError
)

# Test valid transition
try:
    validate_referral_transition('PENDING', 'ACCEPTED')
    print("✓ Valid transition")
except StateMachineError:
    print("✗ Invalid transition")

# Test invalid transition
try:
    validate_referral_transition('PENDING', 'COMPLETED')
    print("✗ Should have failed")
except StateMachineError as e:
    print(f"✓ Correctly rejected: {e}")
```

---

## Integration Patterns

### Pattern 1: Simple Status Update
```python
try:
    validate_referral_transition(referral.status, new_status)
except StateMachineError as e:
    return Response({"message": str(e)}, status=400)

referral.status = new_status
referral.save()
```

### Pattern 2: With Additional Validation
```python
# Check permissions first
if not user_can_transition(request.user):
    return Response({"message": "Permission denied"}, status=403)

# Then validate state machine
try:
    validate_referral_transition(referral.status, new_status)
except StateMachineError as e:
    return Response({"message": str(e)}, status=400)

# Then update
referral.status = new_status
referral.save()
```

### Pattern 3: With Timestamps
```python
try:
    validate_lab_order_transition(order.status, 'resulted')
except StateMachineError as e:
    return Response({"message": str(e)}, status=400)

now = timezone.now()
order.status = 'resulted'
order.resulted_at = now
order.save(update_fields=['status', 'resulted_at'])
```

---

## Troubleshooting

**Problem:** Invalid transition error when updating status

**Solution:** 
1. Check the current status value
2. Verify against valid transitions table above
3. Review the error message for allowed transitions
4. Ensure status value matches exactly (case-sensitive for lab/visit, uppercase for referral)

**Problem:** StateMachineError not caught

**Solution:**
1. Ensure import includes `StateMachineError`
2. Check exception handler is at correct indentation level
3. Verify try/except surrounds validation call

**Problem:** Status updates working in some views but not others

**Solution:**
1. Check all views have state machine validation
2. Ensure all imports are correct
3. Verify validation happens before database update
4. Check for duplicate code paths

---

## Key Points

✓ Always validate before updating status
✓ Use descriptive error messages from StateMachineError
✓ Terminal states cannot transition to any other state
✓ No status can transition to itself (treated as valid no-op)
✓ Check imports and exception handling carefully
✓ Validation is intentionally strict for data integrity
✓ Works alongside role-based access control, not instead of it

---

## Support

For questions about state machines:
1. Review BACKEND_HARDENING_2_2_STATE_MACHINES.md for details
2. Check IMPLEMENTATION_SUMMARY_STATE_MACHINES.txt for overview
3. Look at examples in referral_views.py, lab_views.py, encounter_views.py
4. Review state_machines.py source code and comments
