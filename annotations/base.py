"""
Ultra PDF Editor - Annotation Base Classes
Base classes and utilities for PDF annotations
"""
from dataclasses import dataclass, field
from typing import List, Optional, Tuple, Dict, Any
from enum import Enum
from abc import ABC, abstractmethod
import fitz


class AnnotationType(Enum):
    """Types of annotations supported"""
    HIGHLIGHT = "highlight"
    UNDERLINE = "underline"
    STRIKETHROUGH = "strikethrough"
    SQUIGGLY = "squiggly"
    TEXT_NOTE = "text_note"  # Sticky note
    FREETEXT = "freetext"  # Text box
    LINE = "line"
    ARROW = "arrow"
    RECTANGLE = "rectangle"
    CIRCLE = "circle"
    POLYGON = "polygon"
    POLYLINE = "polyline"
    INK = "ink"  # Freehand
    STAMP = "stamp"
    CARET = "caret"
    FILEATTACHMENT = "fileattachment"
    REDACTION = "redaction"
    LINK = "link"


@dataclass
class Color:
    """RGB color representation"""
    r: float  # 0.0 - 1.0
    g: float
    b: float
    a: float = 1.0  # Alpha

    @classmethod
    def from_hex(cls, hex_color: str) -> 'Color':
        """Create color from hex string (e.g., '#FF0000')"""
        hex_color = hex_color.lstrip('#')
        r = int(hex_color[0:2], 16) / 255
        g = int(hex_color[2:4], 16) / 255
        b = int(hex_color[4:6], 16) / 255
        a = int(hex_color[6:8], 16) / 255 if len(hex_color) == 8 else 1.0
        return cls(r, g, b, a)

    @classmethod
    def from_rgb(cls, r: int, g: int, b: int, a: int = 255) -> 'Color':
        """Create color from RGB values (0-255)"""
        return cls(r / 255, g / 255, b / 255, a / 255)

    def to_tuple(self) -> Tuple[float, float, float]:
        """Convert to tuple (r, g, b)"""
        return (self.r, self.g, self.b)

    def to_hex(self) -> str:
        """Convert to hex string"""
        r = int(self.r * 255)
        g = int(self.g * 255)
        b = int(self.b * 255)
        return f"#{r:02x}{g:02x}{b:02x}"

    def with_alpha(self, alpha: float) -> 'Color':
        """Return a new color with different alpha"""
        return Color(self.r, self.g, self.b, alpha)


# Predefined colors
class Colors:
    RED = Color(1.0, 0.0, 0.0)
    GREEN = Color(0.0, 1.0, 0.0)
    BLUE = Color(0.0, 0.0, 1.0)
    YELLOW = Color(1.0, 1.0, 0.0)
    CYAN = Color(0.0, 1.0, 1.0)
    MAGENTA = Color(1.0, 0.0, 1.0)
    WHITE = Color(1.0, 1.0, 1.0)
    BLACK = Color(0.0, 0.0, 0.0)
    ORANGE = Color(1.0, 0.65, 0.0)
    PINK = Color(1.0, 0.75, 0.8)


@dataclass
class Rect:
    """Rectangle representation"""
    x0: float
    y0: float
    x1: float
    y1: float

    @classmethod
    def from_points(cls, p1: Tuple[float, float], p2: Tuple[float, float]) -> 'Rect':
        """Create from two corner points"""
        x0 = min(p1[0], p2[0])
        y0 = min(p1[1], p2[1])
        x1 = max(p1[0], p2[0])
        y1 = max(p1[1], p2[1])
        return cls(x0, y0, x1, y1)

    @classmethod
    def from_fitz(cls, fitz_rect: fitz.Rect) -> 'Rect':
        """Create from fitz.Rect"""
        return cls(fitz_rect.x0, fitz_rect.y0, fitz_rect.x1, fitz_rect.y1)

    def to_fitz(self) -> fitz.Rect:
        """Convert to fitz.Rect"""
        return fitz.Rect(self.x0, self.y0, self.x1, self.y1)

    def to_tuple(self) -> Tuple[float, float, float, float]:
        """Convert to tuple"""
        return (self.x0, self.y0, self.x1, self.y1)

    @property
    def width(self) -> float:
        return self.x1 - self.x0

    @property
    def height(self) -> float:
        return self.y1 - self.y0

    @property
    def center(self) -> Tuple[float, float]:
        return ((self.x0 + self.x1) / 2, (self.y0 + self.y1) / 2)

    def contains(self, x: float, y: float) -> bool:
        """Check if point is inside rectangle"""
        return self.x0 <= x <= self.x1 and self.y0 <= y <= self.y1

    def intersects(self, other: 'Rect') -> bool:
        """Check if rectangles intersect"""
        return not (self.x1 < other.x0 or self.x0 > other.x1 or
                    self.y1 < other.y0 or self.y0 > other.y1)

    def expand(self, amount: float) -> 'Rect':
        """Return expanded rectangle"""
        return Rect(
            self.x0 - amount,
            self.y0 - amount,
            self.x1 + amount,
            self.y1 + amount
        )


@dataclass
class AnnotationProperties:
    """Common properties for all annotations"""
    author: str = ""
    subject: str = ""
    contents: str = ""  # Note/comment text
    creation_date: str = ""
    modification_date: str = ""
    opacity: float = 1.0
    flags: int = 0  # PDF annotation flags


@dataclass
class Annotation(ABC):
    """Base class for all annotations"""
    type: AnnotationType
    page: int
    rect: Rect
    color: Color = field(default_factory=lambda: Colors.YELLOW)
    properties: AnnotationProperties = field(default_factory=AnnotationProperties)

    # Internal reference to fitz annotation (if created)
    _fitz_annot: Optional[Any] = field(default=None, repr=False)

    @abstractmethod
    def create_on_page(self, page: fitz.Page) -> fitz.Annot:
        """Create this annotation on a PDF page"""
        pass

    @abstractmethod
    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary"""
        pass

    @classmethod
    @abstractmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Annotation':
        """Deserialize from dictionary"""
        pass

    def update(self):
        """Update the annotation after property changes"""
        if self._fitz_annot:
            self._fitz_annot.update()


@dataclass
class TextMarkupAnnotation(Annotation):
    """Annotation for text markup (highlight, underline, strikethrough)"""
    quads: List[Tuple[float, ...]] = field(default_factory=list)  # Text quads

    def create_on_page(self, page: fitz.Page) -> fitz.Annot:
        """Create text markup annotation"""
        fitz_rect = self.rect.to_fitz()

        if self.type == AnnotationType.HIGHLIGHT:
            annot = page.add_highlight_annot(fitz_rect)
        elif self.type == AnnotationType.UNDERLINE:
            annot = page.add_underline_annot(fitz_rect)
        elif self.type == AnnotationType.STRIKETHROUGH:
            annot = page.add_strikeout_annot(fitz_rect)
        elif self.type == AnnotationType.SQUIGGLY:
            annot = page.add_squiggly_annot(fitz_rect)
        else:
            raise ValueError(f"Invalid text markup type: {self.type}")

        annot.set_colors(stroke=self.color.to_tuple())
        annot.set_opacity(self.properties.opacity)

        if self.properties.contents:
            annot.set_info(content=self.properties.contents)

        annot.update()
        self._fitz_annot = annot
        return annot

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": self.type.value,
            "page": self.page,
            "rect": self.rect.to_tuple(),
            "color": self.color.to_hex(),
            "opacity": self.properties.opacity,
            "contents": self.properties.contents,
            "quads": self.quads,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'TextMarkupAnnotation':
        return cls(
            type=AnnotationType(data["type"]),
            page=data["page"],
            rect=Rect(*data["rect"]),
            color=Color.from_hex(data["color"]),
            properties=AnnotationProperties(
                opacity=data.get("opacity", 1.0),
                contents=data.get("contents", ""),
            ),
            quads=data.get("quads", []),
        )


@dataclass
class TextAnnotation(Annotation):
    """Sticky note annotation"""
    icon: str = "Note"  # Note, Comment, Help, Insert, Key, NewParagraph, Paragraph

    def __post_init__(self):
        self.type = AnnotationType.TEXT_NOTE

    def create_on_page(self, page: fitz.Page) -> fitz.Annot:
        """Create sticky note annotation"""
        point = fitz.Point(self.rect.x0, self.rect.y0)
        annot = page.add_text_annot(point, self.properties.contents, icon=self.icon)
        annot.set_colors(stroke=self.color.to_tuple())
        annot.update()
        self._fitz_annot = annot
        return annot

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": self.type.value,
            "page": self.page,
            "rect": self.rect.to_tuple(),
            "color": self.color.to_hex(),
            "contents": self.properties.contents,
            "icon": self.icon,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'TextAnnotation':
        return cls(
            type=AnnotationType.TEXT_NOTE,
            page=data["page"],
            rect=Rect(*data["rect"]),
            color=Color.from_hex(data["color"]),
            properties=AnnotationProperties(contents=data.get("contents", "")),
            icon=data.get("icon", "Note"),
        )


@dataclass
class FreeTextAnnotation(Annotation):
    """Text box annotation"""
    text: str = ""
    font_name: str = "helv"
    font_size: float = 12.0
    text_color: Color = field(default_factory=lambda: Colors.BLACK)
    fill_color: Optional[Color] = field(default_factory=lambda: Colors.WHITE)
    border_width: float = 1.0
    align: int = 0  # 0=left, 1=center, 2=right

    def __post_init__(self):
        self.type = AnnotationType.FREETEXT

    def create_on_page(self, page: fitz.Page) -> fitz.Annot:
        """Create free text annotation"""
        annot = page.add_freetext_annot(
            self.rect.to_fitz(),
            self.text,
            fontsize=self.font_size,
            fontname=self.font_name,
            text_color=self.text_color.to_tuple(),
            fill_color=self.fill_color.to_tuple() if self.fill_color else None,
            align=self.align,
        )
        annot.set_border(width=self.border_width)
        annot.update()
        self._fitz_annot = annot
        return annot

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": self.type.value,
            "page": self.page,
            "rect": self.rect.to_tuple(),
            "text": self.text,
            "font_name": self.font_name,
            "font_size": self.font_size,
            "text_color": self.text_color.to_hex(),
            "fill_color": self.fill_color.to_hex() if self.fill_color else None,
            "border_width": self.border_width,
            "align": self.align,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'FreeTextAnnotation':
        return cls(
            type=AnnotationType.FREETEXT,
            page=data["page"],
            rect=Rect(*data["rect"]),
            text=data.get("text", ""),
            font_name=data.get("font_name", "helv"),
            font_size=data.get("font_size", 12.0),
            text_color=Color.from_hex(data.get("text_color", "#000000")),
            fill_color=Color.from_hex(data["fill_color"]) if data.get("fill_color") else None,
            border_width=data.get("border_width", 1.0),
            align=data.get("align", 0),
        )


@dataclass
class ShapeAnnotation(Annotation):
    """Shape annotations (rectangle, circle, line)"""
    stroke_color: Color = field(default_factory=lambda: Colors.RED)
    fill_color: Optional[Color] = None
    stroke_width: float = 1.0
    # For lines
    start_point: Optional[Tuple[float, float]] = None
    end_point: Optional[Tuple[float, float]] = None
    # Line endings
    line_end_start: str = "None"  # None, Square, Circle, Diamond, OpenArrow, ClosedArrow
    line_end_end: str = "None"

    def create_on_page(self, page: fitz.Page) -> fitz.Annot:
        """Create shape annotation"""
        if self.type == AnnotationType.RECTANGLE:
            annot = page.add_rect_annot(self.rect.to_fitz())
        elif self.type == AnnotationType.CIRCLE:
            annot = page.add_circle_annot(self.rect.to_fitz())
        elif self.type in (AnnotationType.LINE, AnnotationType.ARROW):
            if self.start_point and self.end_point:
                annot = page.add_line_annot(
                    fitz.Point(self.start_point),
                    fitz.Point(self.end_point)
                )
                if self.type == AnnotationType.ARROW:
                    annot.set_line_ends(fitz.PDF_ANNOT_LE_NONE, fitz.PDF_ANNOT_LE_OPEN_ARROW)
            else:
                raise ValueError("Line annotation requires start and end points")
        else:
            raise ValueError(f"Invalid shape type: {self.type}")

        annot.set_colors(
            stroke=self.stroke_color.to_tuple(),
            fill=self.fill_color.to_tuple() if self.fill_color else None
        )
        annot.set_border(width=self.stroke_width)
        annot.set_opacity(self.properties.opacity)
        annot.update()

        self._fitz_annot = annot
        return annot

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": self.type.value,
            "page": self.page,
            "rect": self.rect.to_tuple(),
            "stroke_color": self.stroke_color.to_hex(),
            "fill_color": self.fill_color.to_hex() if self.fill_color else None,
            "stroke_width": self.stroke_width,
            "opacity": self.properties.opacity,
            "start_point": self.start_point,
            "end_point": self.end_point,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ShapeAnnotation':
        return cls(
            type=AnnotationType(data["type"]),
            page=data["page"],
            rect=Rect(*data["rect"]),
            stroke_color=Color.from_hex(data.get("stroke_color", "#FF0000")),
            fill_color=Color.from_hex(data["fill_color"]) if data.get("fill_color") else None,
            stroke_width=data.get("stroke_width", 1.0),
            properties=AnnotationProperties(opacity=data.get("opacity", 1.0)),
            start_point=data.get("start_point"),
            end_point=data.get("end_point"),
        )


@dataclass
class InkAnnotation(Annotation):
    """Freehand drawing annotation"""
    paths: List[List[Tuple[float, float]]] = field(default_factory=list)
    stroke_width: float = 2.0

    def __post_init__(self):
        self.type = AnnotationType.INK

    def create_on_page(self, page: fitz.Page) -> fitz.Annot:
        """Create ink annotation"""
        ink_list = [[fitz.Point(p) for p in path] for path in self.paths]
        annot = page.add_ink_annot(ink_list)
        annot.set_colors(stroke=self.color.to_tuple())
        annot.set_border(width=self.stroke_width)
        annot.set_opacity(self.properties.opacity)
        annot.update()

        self._fitz_annot = annot
        return annot

    def add_point(self, point: Tuple[float, float], new_path: bool = False):
        """Add a point to the current path"""
        if new_path or not self.paths:
            self.paths.append([point])
        else:
            self.paths[-1].append(point)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": self.type.value,
            "page": self.page,
            "rect": self.rect.to_tuple(),
            "color": self.color.to_hex(),
            "stroke_width": self.stroke_width,
            "opacity": self.properties.opacity,
            "paths": self.paths,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'InkAnnotation':
        return cls(
            type=AnnotationType.INK,
            page=data["page"],
            rect=Rect(*data["rect"]),
            color=Color.from_hex(data.get("color", "#000000")),
            properties=AnnotationProperties(opacity=data.get("opacity", 1.0)),
            paths=data.get("paths", []),
            stroke_width=data.get("stroke_width", 2.0),
        )


@dataclass
class StampAnnotation(Annotation):
    """Stamp annotation"""
    stamp_name: str = "Approved"
    # Predefined stamps: Approved, Experimental, NotApproved, AsIs, Expired,
    # NotForPublicRelease, Confidential, Final, Sold, Departmental,
    # ForComment, TopSecret, Draft, ForPublicRelease

    def __post_init__(self):
        self.type = AnnotationType.STAMP

    def create_on_page(self, page: fitz.Page) -> fitz.Annot:
        """Create stamp annotation"""
        annot = page.add_stamp_annot(self.rect.to_fitz(), stamp=self.stamp_name)
        annot.set_opacity(self.properties.opacity)
        annot.update()

        self._fitz_annot = annot
        return annot

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": self.type.value,
            "page": self.page,
            "rect": self.rect.to_tuple(),
            "stamp_name": self.stamp_name,
            "opacity": self.properties.opacity,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'StampAnnotation':
        return cls(
            type=AnnotationType.STAMP,
            page=data["page"],
            rect=Rect(*data["rect"]),
            stamp_name=data.get("stamp_name", "Approved"),
            properties=AnnotationProperties(opacity=data.get("opacity", 1.0)),
        )


@dataclass
class RedactionAnnotation(Annotation):
    """Redaction annotation (for permanent content removal)"""
    fill_color: Color = field(default_factory=lambda: Colors.BLACK)

    def __post_init__(self):
        self.type = AnnotationType.REDACTION

    def create_on_page(self, page: fitz.Page) -> fitz.Annot:
        """Create redaction annotation"""
        annot = page.add_redact_annot(self.rect.to_fitz(), fill=self.fill_color.to_tuple())
        self._fitz_annot = annot
        return annot

    def apply(self, page: fitz.Page):
        """Apply the redaction (permanently removes content)"""
        page.apply_redactions()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": self.type.value,
            "page": self.page,
            "rect": self.rect.to_tuple(),
            "fill_color": self.fill_color.to_hex(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'RedactionAnnotation':
        return cls(
            type=AnnotationType.REDACTION,
            page=data["page"],
            rect=Rect(*data["rect"]),
            fill_color=Color.from_hex(data.get("fill_color", "#000000")),
        )


def create_annotation_from_dict(data: Dict[str, Any]) -> Annotation:
    """Factory function to create annotation from dictionary"""
    annot_type = AnnotationType(data["type"])

    if annot_type in (AnnotationType.HIGHLIGHT, AnnotationType.UNDERLINE,
                      AnnotationType.STRIKETHROUGH, AnnotationType.SQUIGGLY):
        return TextMarkupAnnotation.from_dict(data)
    elif annot_type == AnnotationType.TEXT_NOTE:
        return TextAnnotation.from_dict(data)
    elif annot_type == AnnotationType.FREETEXT:
        return FreeTextAnnotation.from_dict(data)
    elif annot_type in (AnnotationType.RECTANGLE, AnnotationType.CIRCLE,
                        AnnotationType.LINE, AnnotationType.ARROW):
        return ShapeAnnotation.from_dict(data)
    elif annot_type == AnnotationType.INK:
        return InkAnnotation.from_dict(data)
    elif annot_type == AnnotationType.STAMP:
        return StampAnnotation.from_dict(data)
    elif annot_type == AnnotationType.REDACTION:
        return RedactionAnnotation.from_dict(data)
    else:
        raise ValueError(f"Unknown annotation type: {annot_type}")
