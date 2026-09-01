
DESTRUCTIVE_PHRASES = [
    "delete", "remove", "drop table", "drop the", "update ", "modify",
    "change the", "erase", "wipe", "truncate", "destroy", "overwrite",
    "insert a", "insert into", "add a new row", "add a row", "create a table",
    "alter table", "replace all",
]

UNANSWERABLE_HINTS = {
    "salary": "employee pay/salary information is not stored anywhere in this database",
    "wage": "pay information is not stored in this database",
    "bonus": "pay/bonus information is not stored in this database",
    "phone": "no phone number column exists for customers or employees",
    "password": "no authentication/password data is stored in this database",
    "credit card": "no payment card details are stored in this database",
    "ssn": "no government ID data is stored in this database",
    "social security": "no government ID data is stored in this database",
    "weather": "this is a music store database; it has no weather data",
    "stock price": "this database has no stock market data",
    "competitor": "this database has no data about competitors",
    "marketing budget": "no marketing/budget data is stored in this database",
    "website traffic": "no web analytics data is stored in this database",
    "date of birth": "no date-of-birth field exists for customers or employees",
    "birthday": "no date-of-birth field exists for customers or employees",
    "performance review": "no employee performance-review data is stored in this database",
    "employee rating": "no employee performance-review data is stored in this database",
    "shipping address": "only a city and country are stored, not a full street address",
    "discount code": "no discount/coupon data is stored in this database",
    "warranty": "no warranty data is stored in this database",
}

def check_destructive_intent(question):
    lower = question.lower()
    return any(phrase in lower for phrase in DESTRUCTIVE_PHRASES)

def check_obviously_unanswerable(question):
    lower = question.lower()
    for hint, reason in UNANSWERABLE_HINTS.items():
        if hint in lower:
            return True, reason
    return False, None
