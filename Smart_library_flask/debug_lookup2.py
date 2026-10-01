import requests

response = requests.get(
    "https://www.googleapis.com/books/v1/volumes",
    params={
        "q": "intitle:The Great Gatsby",
        "key": "AIzaSyA3vkD-8HuO8qy_wJq1-NzWOD31v3eZ1qY"
    }
)

print("Status code:", response.status_code)
print("Response:", response.json())
