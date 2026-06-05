from secrets_manager import get_secret_value
from .homebox import HomeboxService
from .mealie import MealieService
from .enrichers import PriceBuddyService, ChangeDetectionService
from .gmail_ingestor import GmailIngestor
from .receipt_wrangler import ReceiptWranglerClient

SERVICES = {
    "homebox": HomeboxService(),
    "mealie": MealieService(),
    "pricebuddy": PriceBuddyService(),
    "changedetection": ChangeDetectionService()
}

gmail_ingestor = GmailIngestor(get_secret_value)
receipt_wrangler_client = ReceiptWranglerClient(get_secret_value)
