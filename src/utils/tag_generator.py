# src/utils/tag_generator.py
import random
from typing import Optional


def tag_generator(firstname: str, lastname: Optional[str]) -> str:
    # cleaning and lowercasing first name
    clean_firstname = firstname.strip().lower()
    if lastname and lastname.strip():
        clean_lastname = lastname.strip().lower()
        max_slice = random.randint(3, 5)
        last_name = clean_lastname[0:max_slice]
    else:
        last_name = "padi"
    random_number = random.randint(100, 9999)
    tag = f"@{clean_firstname}{last_name}{random_number}"
    return tag
