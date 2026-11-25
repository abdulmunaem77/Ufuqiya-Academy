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

    @app.cli.command("backup-db")
    @click.option("--out", default="backups", show_default=True, help="Directory for the backup file.")
    @click.option("--keep", default=0, type=int, help="Keep only the newest N backups (0 = keep all).")
    def backup_db(out, keep):
        """Write a timestamped backup of the configured database."""
        from .backup import BackupError, backup
        try:
            path = backup(current_app.config["SQLALCHEMY_DATABASE_URI"], out, keep)
        except BackupError as exc:
            raise click.ClickException(str(exc))
        click.echo(f"Backup written: {path}")

    @app.cli.command("restore-db")
    @click.argument("file", type=click.Path(exists=True, dir_okay=False))
    @click.option("--yes", is_flag=True, help="Confirm that the current data will be replaced.")
    @click.option("--safety-dir", default="backups", show_default=True)
    def restore_db(file, yes, safety_dir):
        """Replace the configured database with FILE (a safety backup is taken first)."""
        from .backup import BackupError, restore
        if not yes:
            raise click.ClickException("This REPLACES the current database. Re-run with --yes to confirm.")
        try:
            safety = restore(current_app.config["SQLALCHEMY_DATABASE_URI"], file, safety_dir)
        except BackupError as exc:
            raise click.ClickException(str(exc))
        click.echo("Restore complete." + (f" Previous state saved at: {safety}" if safety else ""))

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
