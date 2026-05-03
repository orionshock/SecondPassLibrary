from django.db import models

from core.models import TimeStampedModel


class Author(TimeStampedModel):
    name = models.CharField(max_length=255)
    biography = models.TextField(blank=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class Series(TimeStampedModel):
    name = models.CharField(max_length=255)
    summary = models.TextField(blank=True)

    class Meta:
        verbose_name_plural = 'series'
        ordering = ['name']

    def __str__(self):
        return self.name


class Book(TimeStampedModel):
    title = models.CharField(max_length=512)
    subtitle = models.CharField(max_length=512, blank=True)
    summary = models.TextField(blank=True)
    authors = models.ManyToManyField(Author, related_name='books', blank=True)
    series = models.ForeignKey(
        Series,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='books',
    )

    class Meta:
        ordering = ['title']

    def __str__(self):
        return self.title


class BookMetadata(TimeStampedModel):
    book = models.OneToOneField(Book, on_delete=models.CASCADE, related_name='metadata')
    publisher = models.CharField(max_length=255, blank=True)
    language = models.CharField(max_length=64, blank=True)
    published_date = models.DateField(null=True, blank=True)
    isbn = models.CharField(max_length=64, blank=True)
    subjects = models.JSONField(blank=True, null=True, default=list)

    def __str__(self):
        return f'Metadata for {self.book.title}'


class BookFile(TimeStampedModel):
    FORMAT_EPUB = 'epub'
    FORMAT_CHOICES = [
        (FORMAT_EPUB, 'EPUB'),
    ]

    book = models.ForeignKey(Book, on_delete=models.CASCADE, related_name='files')
    file = models.FileField(upload_to='epubs/')
    format = models.CharField(max_length=32, choices=FORMAT_CHOICES, default=FORMAT_EPUB)
    checksum = models.CharField(max_length=128, blank=True, null=True, help_text='SHA-256 hash for duplicate detection')

    class Meta:
        ordering = ['book', 'created_at']

    def __str__(self):
        return f'{self.book.title} - {self.file.name}'
