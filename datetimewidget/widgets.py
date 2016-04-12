
__author__ = 'Alfredo Saglimbeni'

from datetime import datetime
import re
import uuid

from django.forms import forms, widgets
from django.forms.widgets import MultiWidget, DateTimeInput, DateInput, TimeInput
from django.utils.formats import get_format, get_language
from django.utils.safestring import mark_safe
from django.utils.six import string_types

try:
    from django.forms.widgets import to_current_timezone
except ImportError:
    to_current_timezone = lambda obj: obj # passthrough, no tz support


# This should be updated as more .po files are added to the datetime picker javascript code
supported_languages = set([
    'ar',
    'bg',
    'ca', 'cs',
    'da', 'de',
    'ee', 'el', 'es','eu',
    'fi', 'fr',
    'he', 'hr', 'hu',
    'id', 'is', 'it',
    'ja',
    'ko', 'kr',
    'lt', 'lv',
    'ms',
    'nb', 'nl', 'no',
    'pl', 'pt-BR', 'pt',
    'ro', 'rs', 'rs-latin', 'ru',
    'sk', 'sl', 'sv', 'sw',
    'th', 'tr',
    'ua', 'uk',
    'zh-CN', 'zh-TW',
    ])


def get_supported_language(language_country_code):
    """Helps us get from django's 'language-countryCode' to the datepicker's 'language' if we
    possibly can.

    If we pass the django 'language_countryCode' through untouched then it might not
    match an exact language string supported by the datepicker and would default to English which
    would be worse than trying to match the language part.
    """

    # Catch empty strings in case one sneeks in
    if not language_country_code:
        return 'en'

    # Check full language & country code against the supported languages as there are dual entries
    # in the list eg. zh-CN (assuming that is a language country code)
    if language_country_code in supported_languages:
        return language_country_code

    # Grab just the language part and try that
    language = language_country_code.split('-')[0]
    if language in supported_languages:
        return language

    # Otherwise return English as the default
    return 'en'


# refer to:
#  - https://docs.python.org/2/library/datetime.html
#  - http://momentjs.com/docs/#/displaying/format/
dateConversiontoPython = {
    'ss': '%S', # second
    'mm': '%M', # minute
    'HH': '%H', # 01-23 hour
    'hh': '%I', # 01-12 hour
    'DD': '%d', # day
    'MM': '%m', # month
    'YY': '%y', # year
    'YYYY': '%Y', # year
}

toPython_re = re.compile(r'\b(' + '|'.join(dateConversiontoPython.keys()) + r')\b')


dateConversiontoJavascript = {
    '%M': 'mm',
    '%m': 'MM',
    '%I': 'hh',
    '%H': 'HH',
    '%d': 'DD',
    '%Y': 'YYYY',
    '%y': 'YY',
    '%S': 'ss'
}

toJavascript_re = re.compile(r'(?<!\w)(' + '|'.join(dateConversiontoJavascript.keys()) + r')\b')


BOOTSTRAP_INPUT_TEMPLATE = {
    2: """
       <div id="%(id)s"  class="controls input-append date">
           %(rendered_widget)s
           %(clear_button)s
           <span class="add-on"><i class="icon-th"></i></span>
       </div>
       <script type="text/javascript">
           $("#%(id)s").datetimepicker({%(options)s});
       </script>
       """,
    3: """
       <div id="%(id)s" class="input-group date">
           %(rendered_widget)s
           %(clear_button)s
           <span class="input-group-addon"><span class="glyphicon %(glyphicon)s"></span></span>
       </div>
       <script type="text/javascript">
           $(function () {
               $("#%(id)s").datetimepicker({%(options)s}).find('input').addClass("form-control");
           });
       </script>
       """
       }

CLEAR_BTN_TEMPLATE = {2: """<span class="add-on"><i class="icon-remove"></i></span>""",
                      3: """<span class="input-group-addon"><span class="glyphicon glyphicon-remove"></span></span>"""}


quoted_options = set([
    'format',
    'defaultDate',
    'disabledDates',
    'enabledDates',
    'useCurrent',
    'icons',
    'viewMode',  # Accepts: 'decades','years','months','days'
    'locale',
    'daysOfWeekDisabled',
    'dayViewHeaderFormat',
    'stepping',
    'minDate',
    'maxDate',
    'toolbarPlacement',  # Accepts: 'default', 'top', 'bottom'
    'widgetPositioning',
    'widgetParent',
    'tooltips',
    ])

# to traslate boolean object to javascript
quoted_bool_options = set([
    'useCurrent',
    'inline',
    'sideBySide',
    'extraFormats',
    'collapse',
    'useStrict',
    'calendarWeeks',
    'showTodayButton',
    'showClear',
    'showClose',
    'keepOpen',
    'keepInvalid',
    'debug',
    'ignoreReadonly',
    'disabledTimeIntervals',
    'allowInputToggle',
    'focusOnShow',
    'enabledHours',
    'disabledHours',
    'viewDate',
    ])


def quote(key, value):
    """Certain options support string values. We want clients to be able to pass Python strings in
    but we need them to be quoted in the output. Unfortunately some of those options also allow
    numbers so we type check the value before wrapping it in quotes.
    """

    if key in quoted_options and isinstance(value, string_types):
        return "'%s'" % value

    if key in quoted_bool_options and isinstance(value, bool):
        return {True:'true',False:'false'}[value]

    return value


class PickerWidgetMixin(object):

    format_name = None
    glyphicon = None

    def __init__(self, attrs=None, options=None, usel10n=None, bootstrap_version=3):

        if bootstrap_version in [2,3]:
            self.bootstrap_version = bootstrap_version
        else:
            # default 2 to mantain support to old implemetation of django-datetime-widget
            self.bootstrap_version = 3

        if attrs is None:
            attrs = {}

        self.options = options

        self.is_localized = False
        self.format = None

        # We want to have a Javascript style date format specifier in the options dictionary and we
        # want a Python style date format specifier as a member variable for parsing the date string
        # from the form data
        if usel10n is True:
            # If we're doing localisation, get the local Python date format and convert it to
            # Javascript data format for the options dictionary
            self.is_localized = True

            # Get format from django format system
            self.format = get_format(self.format_name)[0]

            # Convert Python format specifier to Javascript format specifier
            self.options['format'] = toJavascript_re.sub(
                lambda x: dateConversiontoJavascript[x.group()],
                self.format
                )

            # Set the local language
            self.options['locale'] = get_supported_language(get_language())

        else:

            # If we're not doing localisation, get the Javascript date format provided by the user,
            # with a default, and convert it to a Python data format for later string parsing
            format = self.options['format']
            self.format = toPython_re.sub(
                lambda x: dateConversiontoPython[x.group()],
                format
                )

        super(PickerWidgetMixin, self).__init__(attrs, format=self.format)

    def render(self, name, value, attrs=None):
        final_attrs = self.build_attrs(attrs)
        rendered_widget = super(PickerWidgetMixin, self).render(name, value, final_attrs)

        #if not set, autoclose have to be true.
        self.options.setdefault('keepOpen', False)

        # Build javascript options out of python dictionary
        options_list = []
        for key, value in iter(self.options.items()):
            options_list.append("%s: %s" % (key, quote(key, value)))

        js_options = ",\n".join(options_list)

        # Use provided id or generate hex to avoid collisions in document
        id = final_attrs.get('id', uuid.uuid4().hex)

        clearBtn = quote('showClear', self.options.get('showClear', 'true')) == 'true'

        return mark_safe(
            BOOTSTRAP_INPUT_TEMPLATE[self.bootstrap_version]
                % dict(
                    id=id,
                    rendered_widget=rendered_widget,
                    clear_button=CLEAR_BTN_TEMPLATE[self.bootstrap_version] if clearBtn else "",
                    glyphicon=self.glyphicon,
                    options=js_options
                    )
        )

    def _media(self):

        js = ["js/bootstrap-datetimepicker.js"]

        language = self.options.get('locale', 'en')
        if language != 'en':
            js.append("js/locales/bootstrap-datetimepicker.%s.js" % language)

        return widgets.Media(
            css={
                'all': ('css/datetimepicker.css',)
                },
            js=js
            )

    media = property(_media)


class DateTimeWidget(PickerWidgetMixin, DateTimeInput):
    """
    DateTimeWidget is the corresponding widget for Datetime field, it renders both the date and time
    sections of the datetime picker.
    """

    format_name = 'DATETIME_INPUT_FORMATS'
    glyphicon = 'glyphicon-th'

    def __init__(self, attrs=None, options=None, usel10n=None, bootstrap_version=None):

        if options is None:
            options = {}

        # Set the default options to show only the datepicker object
        options['format'] = options.get('format', 'DD/MM/YYYY HH:mm')

        super(DateTimeWidget, self).__init__(attrs, options, usel10n, bootstrap_version)


class DateWidget(PickerWidgetMixin, DateInput):
    """
    DateWidget is the corresponding widget for Date field, it renders only the date section of
    datetime picker.
    """

    format_name = 'DATE_INPUT_FORMATS'
    glyphicon = 'glyphicon-calendar'

    def __init__(self, attrs=None, options=None, usel10n=None, bootstrap_version=None):

        if options is None:
            options = {}

        # Set the default options to show only the datepicker object
        options['viewMode'] = options.get('viewMode', 'years')
        options['format'] = options.get('format', 'DD/MM/YYYY')

        super(DateWidget, self).__init__(attrs, options, usel10n, bootstrap_version)


class TimeWidget(PickerWidgetMixin, TimeInput):
    """
    TimeWidget is the corresponding widget for Time field, it renders only the time section of
    datetime picker.
    """

    format_name = 'TIME_INPUT_FORMATS'
    glyphicon = 'glyphicon-time'

    def __init__(self, attrs=None, options=None, usel10n=None, bootstrap_version=None):

        if options is None:
            options = {}

        # Set the default options to show only the timepicker object
        options['format'] = options.get('format', 'HH:mm')

        super(TimeWidget, self).__init__(attrs, options, usel10n, bootstrap_version)

