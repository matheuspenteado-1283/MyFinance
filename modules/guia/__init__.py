from flask import Blueprint

bp = Blueprint('guia', __name__)

from . import routes  # noqa
