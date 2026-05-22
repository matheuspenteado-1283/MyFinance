from flask import Blueprint
bp = Blueprint('ai_agent', __name__)
from . import routes  # noqa
