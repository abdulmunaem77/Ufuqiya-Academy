"""Flask CLI: ``flask init-db | seed | create-owner``."""
import re

import click
from flask import current_app
from flask_migrate import upgrade

from owner_config import MIN_PASSWORD_LENGTH, OwnerConfigError, load_owner_settings

from .extensions import db
from .models import ROLE_OWNER, User


def register_cli(app):
    @app.cli.command("init-db")
    def init_db():
        """Create / upgrade the schema using the migration scripts."""
        upgrade()
        click.echo("Database schema is up to date.")

    @app.cli.command("seed")
    @click.option("--force", is_flag=True, help="Seed even if categories already exist.")
    def seed(force):
        """Load clearly-labelled FICTIONAL sample content."""
        from .models import Category
        from .seed import seed_sample_content
        if Category.query.first() and not force:
            click.echo("Content already present; use --force to add the sample set anyway.")
            return
        seed_sample_content()
        click.echo("Sample content loaded (all items flagged as fictional samples).")

    @app.cli.command("create-owner")
    @click.option("--allow-additional", is_flag=True, help="Allow a second owner account.")
    def create_owner(allow_additional):
        """Create the initial owner account (credentials from the environment / prompt)."""
        try:
            cfg = load_owner_settings()
        except OwnerConfigError as exc:
            raise click.ClickException(str(exc))
        if User.query.filter_by(role=ROLE_OWNER).first() and not allow_additional:
            raise click.ClickException("An owner already exists. Use --allow-additional to add another.")
        if User.query.filter_by(email=cfg["email"]).first():
            raise click.ClickException("That e-mail is already registered.")
        from_env = bool(cfg["password"])
        password = cfg["password"]
        if not password:
            password = click.prompt("Owner password", hide_input=True, confirmation_prompt=True)
            if (len(password) < MIN_PASSWORD_LENGTH or not re.search(r"[A-Za-z]", password)
                    or not re.search(r"\d", password)):
                raise click.ClickException(
                    f"Password must be at least {MIN_PASSWORD_LENGTH} characters with letters and digits.")
        user = User(email=cfg["email"], name=cfg["name"], role=ROLE_OWNER,
                    must_change_password=from_env, email_verified=True)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        click.echo(f"Owner account created for {cfg['email']}.")
        if from_env:
            click.echo("The password from the environment must be changed at first login; "
                       "remove OWNER_INITIAL_PASSWORD from your .env now.")
