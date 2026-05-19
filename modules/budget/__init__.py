from flask import Blueprint

bp = Blueprint('budget', __name__)

from . import routes  # noqa
