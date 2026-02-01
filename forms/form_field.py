"""
Ultra PDF Editor - Form Field Classes
Classes for handling PDF form fields
"""
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any, Tuple
from enum import Enum
import fitz


class FieldType(Enum):
    """Types of form fields"""
    TEXT = "text"
    CHECKBOX = "checkbox"
    RADIO = "radio"
    DROPDOWN = "dropdown"
    LISTBOX = "listbox"
    BUTTON = "button"
    SIGNATURE = "signature"


class TextFieldFormat(Enum):
    """Text field formats"""
    NONE = "none"
    NUMBER = "number"
    PERCENTAGE = "percentage"
    DATE = "date"
    TIME = "time"
    SPECIAL = "special"  # SSN, phone, zip


@dataclass
class FieldAppearance:
    """Visual appearance of a form field"""
    font_name: str = "Helvetica"
    font_size: float = 12.0
    text_color: Tuple[float, float, float] = (0, 0, 0)
    fill_color: Optional[Tuple[float, float, float]] = (1, 1, 1)
    border_color: Tuple[float, float, float] = (0, 0, 0)
    border_width: float = 1.0
    border_style: str = "solid"  # solid, dashed, beveled, inset, underline


@dataclass
class FormField:
    """Base class for form fields"""
    name: str
    field_type: FieldType
    page: int
    rect: Tuple[float, float, float, float]  # x0, y0, x1, y1
    value: Any = None
    default_value: Any = None
    tooltip: str = ""
    readonly: bool = False
    required: bool = False
    hidden: bool = False
    appearance: FieldAppearance = field(default_factory=FieldAppearance)

    # Internal fitz reference
    _widget: Optional[Any] = field(default=None, repr=False)

    def create_on_page(self, page: fitz.Page) -> fitz.Widget:
        """Create the form field on a page - to be implemented by subclasses"""
        raise NotImplementedError

    def get_value(self) -> Any:
        """Get current field value"""
        if self._widget:
            return self._widget.field_value
        return self.value

    def set_value(self, value: Any):
        """Set field value"""
        self.value = value
        if self._widget:
            self._widget.field_value = str(value) if value is not None else ""
            self._widget.update()

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary"""
        return {
            "name": self.name,
            "type": self.field_type.value,
            "page": self.page,
            "rect": self.rect,
            "value": self.value,
            "default_value": self.default_value,
            "tooltip": self.tooltip,
            "readonly": self.readonly,
            "required": self.required,
            "hidden": self.hidden,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'FormField':
        """Create from dictionary"""
        field_type = FieldType(data["type"])

        if field_type == FieldType.TEXT:
            return TextField.from_dict(data)
        elif field_type == FieldType.CHECKBOX:
            return CheckboxField.from_dict(data)
        elif field_type == FieldType.RADIO:
            return RadioField.from_dict(data)
        elif field_type == FieldType.DROPDOWN:
            return DropdownField.from_dict(data)
        elif field_type == FieldType.LISTBOX:
            return ListboxField.from_dict(data)
        elif field_type == FieldType.BUTTON:
            return ButtonField.from_dict(data)
        elif field_type == FieldType.SIGNATURE:
            return SignatureField.from_dict(data)
        else:
            raise ValueError(f"Unknown field type: {field_type}")


@dataclass
class TextField(FormField):
    """Text input field"""
    multiline: bool = False
    password: bool = False
    max_length: int = 0  # 0 = unlimited
    format_type: TextFieldFormat = TextFieldFormat.NONE
    comb: bool = False  # Character comb for fixed-width fields
    scroll: bool = True

    def __post_init__(self):
        self.field_type = FieldType.TEXT

    def create_on_page(self, page: fitz.Page) -> fitz.Widget:
        """Create text field widget"""
        widget = fitz.Widget()
        widget.field_name = self.name
        widget.field_type = fitz.PDF_WIDGET_TYPE_TEXT
        widget.rect = fitz.Rect(self.rect)
        widget.field_value = str(self.value) if self.value else ""

        # Set flags
        flags = 0
        if self.multiline:
            flags |= fitz.PDF_TX_FIELD_IS_MULTILINE
        if self.password:
            flags |= fitz.PDF_TX_FIELD_IS_PASSWORD
        if self.readonly:
            flags |= fitz.PDF_FIELD_IS_READ_ONLY
        if self.required:
            flags |= fitz.PDF_FIELD_IS_REQUIRED

        widget.field_flags = flags

        if self.max_length > 0:
            widget.text_maxlen = self.max_length

        # Appearance
        widget.text_fontsize = self.appearance.font_size
        widget.text_color = self.appearance.text_color
        widget.fill_color = self.appearance.fill_color
        widget.border_color = self.appearance.border_color
        widget.border_width = self.appearance.border_width

        self._widget = page.add_widget(widget)
        return self._widget

    def to_dict(self) -> Dict[str, Any]:
        data = super().to_dict()
        data.update({
            "multiline": self.multiline,
            "password": self.password,
            "max_length": self.max_length,
            "format_type": self.format_type.value,
        })
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'TextField':
        return cls(
            name=data["name"],
            field_type=FieldType.TEXT,
            page=data["page"],
            rect=tuple(data["rect"]),
            value=data.get("value"),
            default_value=data.get("default_value"),
            tooltip=data.get("tooltip", ""),
            readonly=data.get("readonly", False),
            required=data.get("required", False),
            multiline=data.get("multiline", False),
            password=data.get("password", False),
            max_length=data.get("max_length", 0),
            format_type=TextFieldFormat(data.get("format_type", "none")),
        )


@dataclass
class CheckboxField(FormField):
    """Checkbox field"""
    checked: bool = False
    export_value: str = "Yes"

    def __post_init__(self):
        self.field_type = FieldType.CHECKBOX

    def create_on_page(self, page: fitz.Page) -> fitz.Widget:
        """Create checkbox widget"""
        widget = fitz.Widget()
        widget.field_name = self.name
        widget.field_type = fitz.PDF_WIDGET_TYPE_CHECKBOX
        widget.rect = fitz.Rect(self.rect)
        widget.field_value = self.export_value if self.checked else "Off"

        flags = 0
        if self.readonly:
            flags |= fitz.PDF_FIELD_IS_READ_ONLY
        if self.required:
            flags |= fitz.PDF_FIELD_IS_REQUIRED
        widget.field_flags = flags

        widget.fill_color = self.appearance.fill_color
        widget.border_color = self.appearance.border_color

        self._widget = page.add_widget(widget)
        return self._widget

    def is_checked(self) -> bool:
        """Check if checkbox is checked"""
        if self._widget:
            return self._widget.field_value != "Off"
        return self.checked

    def toggle(self):
        """Toggle checkbox state"""
        self.checked = not self.is_checked()
        self.set_value(self.export_value if self.checked else "Off")

    def to_dict(self) -> Dict[str, Any]:
        data = super().to_dict()
        data.update({
            "checked": self.checked,
            "export_value": self.export_value,
        })
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'CheckboxField':
        return cls(
            name=data["name"],
            field_type=FieldType.CHECKBOX,
            page=data["page"],
            rect=tuple(data["rect"]),
            tooltip=data.get("tooltip", ""),
            readonly=data.get("readonly", False),
            required=data.get("required", False),
            checked=data.get("checked", False),
            export_value=data.get("export_value", "Yes"),
        )


@dataclass
class RadioField(FormField):
    """Radio button field (part of a radio group)"""
    group_name: str = ""
    selected: bool = False
    export_value: str = ""

    def __post_init__(self):
        self.field_type = FieldType.RADIO

    def create_on_page(self, page: fitz.Page) -> fitz.Widget:
        """Create radio button widget"""
        widget = fitz.Widget()
        widget.field_name = self.group_name or self.name
        widget.field_type = fitz.PDF_WIDGET_TYPE_RADIOBUTTON
        widget.rect = fitz.Rect(self.rect)

        if self.selected:
            widget.field_value = self.export_value

        flags = 0
        if self.readonly:
            flags |= fitz.PDF_FIELD_IS_READ_ONLY
        if self.required:
            flags |= fitz.PDF_FIELD_IS_REQUIRED
        widget.field_flags = flags

        widget.fill_color = self.appearance.fill_color
        widget.border_color = self.appearance.border_color

        self._widget = page.add_widget(widget)
        return self._widget

    def to_dict(self) -> Dict[str, Any]:
        data = super().to_dict()
        data.update({
            "group_name": self.group_name,
            "selected": self.selected,
            "export_value": self.export_value,
        })
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'RadioField':
        return cls(
            name=data["name"],
            field_type=FieldType.RADIO,
            page=data["page"],
            rect=tuple(data["rect"]),
            tooltip=data.get("tooltip", ""),
            readonly=data.get("readonly", False),
            required=data.get("required", False),
            group_name=data.get("group_name", ""),
            selected=data.get("selected", False),
            export_value=data.get("export_value", ""),
        )


@dataclass
class DropdownField(FormField):
    """Dropdown/combo box field"""
    options: List[str] = field(default_factory=list)
    editable: bool = False  # Allow custom input
    selected_index: int = -1

    def __post_init__(self):
        self.field_type = FieldType.DROPDOWN

    def create_on_page(self, page: fitz.Page) -> fitz.Widget:
        """Create dropdown widget"""
        widget = fitz.Widget()
        widget.field_name = self.name
        widget.field_type = fitz.PDF_WIDGET_TYPE_COMBOBOX
        widget.rect = fitz.Rect(self.rect)
        widget.choice_values = self.options

        if 0 <= self.selected_index < len(self.options):
            widget.field_value = self.options[self.selected_index]
        elif self.value:
            widget.field_value = str(self.value)

        flags = 0
        if self.readonly:
            flags |= fitz.PDF_FIELD_IS_READ_ONLY
        if self.required:
            flags |= fitz.PDF_FIELD_IS_REQUIRED
        if self.editable:
            flags |= fitz.PDF_CH_FIELD_IS_EDIT
        widget.field_flags = flags

        widget.text_fontsize = self.appearance.font_size
        widget.text_color = self.appearance.text_color
        widget.fill_color = self.appearance.fill_color

        self._widget = page.add_widget(widget)
        return self._widget

    def to_dict(self) -> Dict[str, Any]:
        data = super().to_dict()
        data.update({
            "options": self.options,
            "editable": self.editable,
            "selected_index": self.selected_index,
        })
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'DropdownField':
        return cls(
            name=data["name"],
            field_type=FieldType.DROPDOWN,
            page=data["page"],
            rect=tuple(data["rect"]),
            value=data.get("value"),
            tooltip=data.get("tooltip", ""),
            readonly=data.get("readonly", False),
            required=data.get("required", False),
            options=data.get("options", []),
            editable=data.get("editable", False),
            selected_index=data.get("selected_index", -1),
        )


@dataclass
class ListboxField(FormField):
    """Listbox field (multiple visible options)"""
    options: List[str] = field(default_factory=list)
    multi_select: bool = False
    selected_indices: List[int] = field(default_factory=list)

    def __post_init__(self):
        self.field_type = FieldType.LISTBOX

    def create_on_page(self, page: fitz.Page) -> fitz.Widget:
        """Create listbox widget"""
        widget = fitz.Widget()
        widget.field_name = self.name
        widget.field_type = fitz.PDF_WIDGET_TYPE_LISTBOX
        widget.rect = fitz.Rect(self.rect)
        widget.choice_values = self.options

        flags = 0
        if self.readonly:
            flags |= fitz.PDF_FIELD_IS_READ_ONLY
        if self.required:
            flags |= fitz.PDF_FIELD_IS_REQUIRED
        if self.multi_select:
            flags |= fitz.PDF_CH_FIELD_IS_MULTI_SELECT
        widget.field_flags = flags

        widget.text_fontsize = self.appearance.font_size
        widget.fill_color = self.appearance.fill_color

        self._widget = page.add_widget(widget)
        return self._widget

    def to_dict(self) -> Dict[str, Any]:
        data = super().to_dict()
        data.update({
            "options": self.options,
            "multi_select": self.multi_select,
            "selected_indices": self.selected_indices,
        })
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ListboxField':
        return cls(
            name=data["name"],
            field_type=FieldType.LISTBOX,
            page=data["page"],
            rect=tuple(data["rect"]),
            tooltip=data.get("tooltip", ""),
            readonly=data.get("readonly", False),
            required=data.get("required", False),
            options=data.get("options", []),
            multi_select=data.get("multi_select", False),
            selected_indices=data.get("selected_indices", []),
        )


@dataclass
class ButtonField(FormField):
    """Push button field"""
    label: str = ""
    action: str = ""  # JavaScript action

    def __post_init__(self):
        self.field_type = FieldType.BUTTON

    def create_on_page(self, page: fitz.Page) -> fitz.Widget:
        """Create button widget"""
        widget = fitz.Widget()
        widget.field_name = self.name
        widget.field_type = fitz.PDF_WIDGET_TYPE_BUTTON
        widget.rect = fitz.Rect(self.rect)
        widget.button_caption = self.label

        widget.fill_color = self.appearance.fill_color
        widget.border_color = self.appearance.border_color
        widget.text_fontsize = self.appearance.font_size

        self._widget = page.add_widget(widget)
        return self._widget

    def to_dict(self) -> Dict[str, Any]:
        data = super().to_dict()
        data.update({
            "label": self.label,
            "action": self.action,
        })
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ButtonField':
        return cls(
            name=data["name"],
            field_type=FieldType.BUTTON,
            page=data["page"],
            rect=tuple(data["rect"]),
            label=data.get("label", ""),
            action=data.get("action", ""),
        )


@dataclass
class SignatureField(FormField):
    """Digital signature field"""
    signed: bool = False
    signer_name: str = ""
    sign_date: str = ""

    def __post_init__(self):
        self.field_type = FieldType.SIGNATURE

    def create_on_page(self, page: fitz.Page) -> fitz.Widget:
        """Create signature field widget"""
        widget = fitz.Widget()
        widget.field_name = self.name
        widget.field_type = fitz.PDF_WIDGET_TYPE_SIGNATURE
        widget.rect = fitz.Rect(self.rect)

        widget.fill_color = self.appearance.fill_color
        widget.border_color = self.appearance.border_color

        self._widget = page.add_widget(widget)
        return self._widget

    def to_dict(self) -> Dict[str, Any]:
        data = super().to_dict()
        data.update({
            "signed": self.signed,
            "signer_name": self.signer_name,
            "sign_date": self.sign_date,
        })
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'SignatureField':
        return cls(
            name=data["name"],
            field_type=FieldType.SIGNATURE,
            page=data["page"],
            rect=tuple(data["rect"]),
            signed=data.get("signed", False),
            signer_name=data.get("signer_name", ""),
            sign_date=data.get("sign_date", ""),
        )


class FormManager:
    """Manager for handling form fields in a document"""

    def __init__(self, document):
        self._document = document
        self._fields: Dict[str, FormField] = {}

    def load_fields(self):
        """Load all form fields from the document"""
        self._fields.clear()

        if not self._document._doc:
            return

        for page_num in range(len(self._document._doc)):
            page = self._document._doc[page_num]

            for widget in page.widgets():
                field = self._widget_to_field(widget, page_num)
                if field:
                    self._fields[field.name] = field

    def _widget_to_field(self, widget: fitz.Widget, page_num: int) -> Optional[FormField]:
        """Convert fitz widget to FormField"""
        field_type = widget.field_type
        name = widget.field_name
        rect = tuple(widget.rect)

        if field_type == fitz.PDF_WIDGET_TYPE_TEXT:
            return TextField(
                name=name,
                field_type=FieldType.TEXT,
                page=page_num,
                rect=rect,
                value=widget.field_value,
                _widget=widget,
            )
        elif field_type == fitz.PDF_WIDGET_TYPE_CHECKBOX:
            return CheckboxField(
                name=name,
                field_type=FieldType.CHECKBOX,
                page=page_num,
                rect=rect,
                checked=widget.field_value != "Off",
                _widget=widget,
            )
        elif field_type == fitz.PDF_WIDGET_TYPE_RADIOBUTTON:
            return RadioField(
                name=name,
                field_type=FieldType.RADIO,
                page=page_num,
                rect=rect,
                _widget=widget,
            )
        elif field_type == fitz.PDF_WIDGET_TYPE_COMBOBOX:
            return DropdownField(
                name=name,
                field_type=FieldType.DROPDOWN,
                page=page_num,
                rect=rect,
                value=widget.field_value,
                options=list(widget.choice_values) if widget.choice_values else [],
                _widget=widget,
            )
        elif field_type == fitz.PDF_WIDGET_TYPE_LISTBOX:
            return ListboxField(
                name=name,
                field_type=FieldType.LISTBOX,
                page=page_num,
                rect=rect,
                options=list(widget.choice_values) if widget.choice_values else [],
                _widget=widget,
            )
        elif field_type == fitz.PDF_WIDGET_TYPE_BUTTON:
            return ButtonField(
                name=name,
                field_type=FieldType.BUTTON,
                page=page_num,
                rect=rect,
                label=widget.button_caption or "",
                _widget=widget,
            )
        elif field_type == fitz.PDF_WIDGET_TYPE_SIGNATURE:
            return SignatureField(
                name=name,
                field_type=FieldType.SIGNATURE,
                page=page_num,
                rect=rect,
                _widget=widget,
            )

        return None

    def get_field(self, name: str) -> Optional[FormField]:
        """Get a field by name"""
        return self._fields.get(name)

    def get_all_fields(self) -> List[FormField]:
        """Get all form fields"""
        return list(self._fields.values())

    def get_fields_on_page(self, page_num: int) -> List[FormField]:
        """Get all fields on a specific page"""
        return [f for f in self._fields.values() if f.page == page_num]

    def add_field(self, field: FormField):
        """Add a new form field"""
        page = self._document._doc[field.page]
        field.create_on_page(page)
        self._fields[field.name] = field
        self._document._is_modified = True

    def remove_field(self, name: str):
        """Remove a form field"""
        if name in self._fields:
            field = self._fields[name]
            if field._widget:
                page = self._document._doc[field.page]
                # Note: fitz doesn't have a direct widget removal method
                # Would need to rebuild the page or use lower-level operations
            del self._fields[name]
            self._document._is_modified = True

    def fill_field(self, name: str, value: Any):
        """Fill a form field with a value"""
        field = self._fields.get(name)
        if field:
            field.set_value(value)
            self._document._is_modified = True

    def export_data(self) -> Dict[str, Any]:
        """Export form data as dictionary"""
        return {name: field.get_value() for name, field in self._fields.items()}

    def import_data(self, data: Dict[str, Any]):
        """Import form data from dictionary"""
        for name, value in data.items():
            self.fill_field(name, value)

    def flatten(self):
        """Flatten form fields (make them non-editable)"""
        # This would convert form fields to static content
        pass
