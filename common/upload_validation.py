import re

import magic
from django.conf import settings
from graphql import GraphQLError


def validate_upload_file(file):
    file.seek(0)
    try:
        file_type = magic.from_buffer(file.read(2048), mime=True)
    finally:
        file.seek(0)
    if not re.match(r"(audio|video|application|text)", file_type):
        raise GraphQLError("File type is not supported")
    if file.size > settings.UPLOAD_FILE_MAX_SIZE:
        raise GraphQLError("File size has exceeded")
    return {"file_type": file_type}
