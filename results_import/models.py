from django.conf import settings
from django.db import models

from races.models import Race, Result, Runner, Season
from results_import import normalise


class ResultsUpload(models.Model):
    """One uploaded results file and everything that was done with it.

    The original file is kept byte for byte in the database, so it survives
    redeploys and is part of the nightly database backup.
    """

    DRAFT, PUBLISHED, REVERTED, DISCARDED = (
        "draft",
        "published",
        "reverted",
        "discarded",
    )
    STATUSES = [
        (DRAFT, "Draft"),
        (PUBLISHED, "Published"),
        (REVERTED, "Reverted"),
        (DISCARDED, "Discarded"),
    ]

    season = models.ForeignKey(Season, on_delete=models.PROTECT)
    race = models.ForeignKey(Race, null=True, blank=True, on_delete=models.SET_NULL)
    race_name = models.CharField(max_length=255)
    race_date = models.DateField(null=True, blank=True)
    description = models.TextField(blank=True)

    original_filename = models.CharField(max_length=255)
    original_file = models.BinaryField()
    sha256 = models.CharField(max_length=64)
    file_headers = models.JSONField(default=list)
    ignored_headers = models.JSONField(default=list)

    status = models.CharField(max_length=10, choices=STATUSES, default=DRAFT)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+"
    )
    uploaded_at = models.DateTimeField(auto_now_add=True)
    published_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+"
    )
    published_at = models.DateTimeField(null=True, blank=True)
    reverted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+"
    )
    reverted_at = models.DateTimeField(null=True, blank=True)
    reopened_from = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="reopened_as",
    )

    # What publishing created, so reverting can remove exactly that.
    versions_before = models.JSONField(default=dict)
    created_runner_ids = models.JSONField(default=list)

    class Meta:
        ordering = ["-uploaded_at", "-id"]

    def __str__(self):
        return f"{self.race_name} {self.season_label} ({self.original_filename})"

    @property
    def season_year(self):
        return self.season.season_start_year

    @property
    def season_label(self):
        return normalise.season_label(self.season_year)

    @property
    def is_draft(self):
        return self.status == self.DRAFT

    @property
    def is_published(self):
        return self.status == self.PUBLISHED


class UploadRow(models.Model):
    """One spreadsheet row: what the file said, and what the site will show."""

    upload = models.ForeignKey(
        ResultsUpload, on_delete=models.CASCADE, related_name="rows"
    )
    number = models.PositiveIntegerField()  # the row number in the spreadsheet
    raw = models.JSONField()

    first_name = models.CharField(max_length=255, blank=True)
    last_name = models.CharField(max_length=255, blank=True)
    bib = models.CharField(max_length=255, blank=True)
    category = models.CharField(max_length=255, blank=True)
    club = models.CharField(max_length=255, blank=True)
    time_text = models.CharField(max_length=32, blank=True)

    runner = models.ForeignKey(Runner, null=True, blank=True, on_delete=models.SET_NULL)
    result = models.ForeignKey(Result, null=True, blank=True, on_delete=models.SET_NULL)

    class Meta:
        ordering = ["number"]
        unique_together = ("upload", "number")

    def __str__(self):
        return f"Row {self.number}: {self.first_name} {self.last_name}"

    @property
    def is_added(self):
        """Typed in by hand; the file has no such row."""
        return bool(self.raw.get("added"))

    def get_value(self, field):
        if field == "name":
            return [self.first_name, self.last_name]
        if field == "time":
            return self.time_text
        return getattr(self, field)

    def set_value(self, field, value):
        if field == "name":
            self.first_name, self.last_name = value
        elif field == "time":
            self.time_text = value
        else:
            setattr(self, field, value)


class RowChange(models.Model):
    """One difference between the file and the site, with who or what made it.

    A change can always be traced: ``before`` and ``after`` hold the values,
    ``affected`` lists every runner record it altered outside this upload's
    own rows, and reverting puts each of those back.
    """

    FIELDS = [
        ("name", "Name"),
        ("club", "Club"),
        ("category", "Category"),
        ("bib", "Number"),
        ("time", "Time"),
    ]
    SOURCES = [
        (normalise.AUTOMATIC, "Automatic"),
        (normalise.REMEMBERED, "Remembered decision"),
        (normalise.DECIDED, "Your decision"),
        (normalise.MANUAL, "Edited by hand"),
    ]
    STATUSES = [
        (normalise.PENDING, "Needs a decision"),
        (normalise.APPLIED, "Applied"),
        (normalise.REVERTED, "Reverted"),
    ]
    # Rule that makes the site use the file's club or number for a runner who
    # already has a record this season.
    UPDATE_RECORD = "update_record"
    # Rule of the change that records a row added by hand: a finisher the
    # file left out. Reverting it removes the row.
    ADDED = "added"

    row = models.ForeignKey(UploadRow, on_delete=models.CASCADE, related_name="changes")
    field = models.CharField(max_length=10, choices=FIELDS)
    before = models.JSONField(null=True)
    after = models.JSONField(null=True)
    rule = models.CharField(max_length=32)
    reason = models.CharField(max_length=500, blank=True)
    source = models.CharField(max_length=10, choices=SOURCES)
    status = models.CharField(max_length=10, choices=STATUSES)
    options = models.JSONField(default=list)
    chosen = models.PositiveSmallIntegerField(null=True, blank=True)
    scope = models.CharField(max_length=10, default="row")
    affected = models.JSONField(default=list)
    note = models.CharField(max_length=500, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+"
    )

    class Meta:
        ordering = ["row__number", "id"]

    def __str__(self):
        return f"{self.get_field_display()} on row {self.row.number}"

    @property
    def is_pending(self):
        return self.status == normalise.PENDING

    @property
    def chosen_option(self):
        if self.chosen is None or self.chosen >= len(self.options):
            return {}
        return self.options[self.chosen]


class ImportRule(models.Model):
    """A decision to apply again the next time the same thing turns up."""

    NAME, CLUB, DIFFERENT = "name", "club", "different"
    KINDS = [
        (NAME, "Name spelling"),
        (CLUB, "Club spelling"),
        (DIFFERENT, "Different people"),
    ]

    kind = models.CharField(max_length=10, choices=KINDS)
    from_key = models.CharField(max_length=600)
    from_label = models.CharField(max_length=600)
    to_value = models.JSONField(null=True)
    to_label = models.CharField(max_length=600, blank=True)
    created_from = models.ForeignKey(
        RowChange,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="rules",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ["kind", "from_label"]

    def __str__(self):
        return f"{self.from_label} → {self.to_label}"
