"""
SMS Integration and Gateway Package for eduManage360.
Exports:
- normalize_ghana_phone
- mask_phone_number
- MultiGatewaySMSEngine, sms_engine
- send_admission_voucher_sms
- send_sms_hubtel (backwards-compatibility)
"""

from .gateway import (
    normalize_ghana_phone,
    mask_phone_number,
    BaseSMSGateway,
    MNotifySMSGateway,
    HubtelSMSGateway,
    MultiGatewaySMSEngine,
    sms_engine,
    send_admission_voucher_sms
)
from .hubtel import send_sms_hubtel, get_hubtel_credentials
