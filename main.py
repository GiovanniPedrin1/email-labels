from typing import Iterable, List
import json
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError


SERVICE_ACCOUNT_FILE = "service-account.json"

SCOPES = [
    "https://www.googleapis.com/auth/gmail.modify",
]

with open("usuarios.json", "r") as file:
    USERS_TO_LABEL = json.load(file)

def chunked(items: List[str], size: int) -> Iterable[List[str]]:
    for i in range(0, len(items), size):
        yield items[i:i + size]


def gmail_service_as(user_email: str):
    credentials = service_account.Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE,
        scopes=SCOPES,
    )

    delegated_credentials = credentials.with_subject(user_email)

    return build(
        "gmail",
        "v1",
        credentials=delegated_credentials,
        cache_discovery=False,
    )


def get_or_create_label(service, user_email: str, label_name: str) -> str:
    labels_response = service.users().labels().list(
        userId=user_email
    ).execute()

    labels = labels_response.get("labels", [])

    for label in labels:
        if label["name"].lower() == label_name.lower():
            return label["id"]

    label_body = {
        "name": label_name,
        "labelListVisibility": "labelShow",
        "messageListVisibility": "show",
    }

    created_label = service.users().labels().create(
        userId=user_email,
        body=label_body,
    ).execute()

    return created_label["id"]


def list_all_message_ids(service, user_email: str, query: str) -> List[str]:
    message_ids = []
    page_token = None

    while True:
        response = service.users().messages().list(
            userId=user_email,
            q=query,
            maxResults=500,
            pageToken=page_token,
            includeSpamTrash=False,
        ).execute()

        messages = response.get("messages", [])
        message_ids.extend(message["id"] for message in messages)

        page_token = response.get("nextPageToken")
        if not page_token:
            break

    return message_ids


def apply_label_to_messages(service, user_email: str, message_ids: List[str], label_id: str):
    for batch in chunked(message_ids, 1000):
        service.users().messages().batchModify(
            userId=user_email,
            body={
                "ids": batch,
                "addLabelIds": [label_id],
            },
        ).execute()


def main():
    for item in USERS_TO_LABEL:
        user_email = item["email"]
        label_name = item["label"]

        print(f"Processando {user_email}...")

        service = gmail_service_as(user_email)

        label_id = get_or_create_label(
            service=service,
            user_email=user_email,
            label_name=label_name,
        )

        message_ids = list_all_message_ids(
            service=service,
            user_email=user_email,
            query="in:anywhere -in:trash",
        )

        print(f"{len(message_ids)} mensagens encontradas para {user_email}.")

        if message_ids:
            apply_label_to_messages(
                service=service,
                user_email=user_email,
                message_ids=message_ids,
                label_id=label_id,
            )

        print(f"Label aplicada: {label_name}")


if __name__ == "__main__":
    try:
        main()
    except HttpError as error:
        print(f"Erro da API: {error}")