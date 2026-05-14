# Mapping Widgets

Param type → Panel widget mapping used by `.from_param()`. Also applies when
Panel auto-generates widgets from Parameterized classes.

## Contents

- [Numeric](#numeric)
- [Text](#text)
- [Selection](#selection)
- [Boolean](#boolean)
- [Date and Time](#date-and-time)
- [Containers](#containers)
- [Special](#special)
- [No Widget](#no-widget)

## Numeric

| Param Type | Condition | Panel Widget | pmui Widget |
|---|---|---|---|
| `param.Integer` | has `bounds` | `pn.widgets.IntSlider` | `pmui.IntSlider` |
| `param.Integer` | no `bounds` | `pn.widgets.IntInput` | `pmui.IntInput` |
| `param.Number` | has `bounds` | `pn.widgets.FloatSlider` | `pmui.FloatSlider` |
| `param.Number` | no `bounds` | `pn.widgets.FloatInput` | `pmui.FloatInput` |
| `param.Range` | — | `pn.widgets.RangeSlider` | `pmui.RangeSlider` |
| `param.NumericTuple` | — | `pn.widgets.LiteralInput` | `pmui.LiteralInput` |

## Text

| Param Type | Condition | Panel Widget | pmui Widget |
|---|---|---|---|
| `param.String` | default | `pn.widgets.TextInput` | `pmui.TextInput` |
| `param.String` | long text (`doc` hint or widget override) | `pn.widgets.TextAreaInput` | `pmui.TextAreaInput` |

## Selection

| Param Type | Condition | Panel Widget | pmui Widget |
|---|---|---|---|
| `param.Selector` | default | `pn.widgets.Select` | `pmui.Select` |
| `param.Selector` | few options (≤3) | `pn.widgets.RadioButtonGroup` | `pmui.RadioButtonGroup` |
| `param.ListSelector` | default | `pn.widgets.MultiSelect` | `pmui.MultiSelect` |
| `param.ListSelector` | few options | `pn.widgets.CheckButtonGroup` | `pmui.CheckButtonGroup` |
| `param.ObjectSelector` | — | `pn.widgets.Select` | `pmui.Select` |
| `param.FileSelector` | — | `pn.widgets.Select` | `pmui.Select` |

## Boolean

| Param Type | Panel Widget | pmui Widget |
|---|---|---|
| `param.Boolean` | `pn.widgets.Checkbox` | `pmui.Switch` |
| `param.Event` | `pn.widgets.Button` | `pmui.Button` |

## Date and Time

| Param Type | Panel Widget | pmui Widget |
|---|---|---|
| `param.Date` | `pn.widgets.DatePicker` | `pmui.DatePicker` |
| `param.DateRange` | `pn.widgets.DateRangePicker` | `pmui.DateRangePicker` |
| `param.CalendarDate` | `pn.widgets.DatePicker` | `pmui.DatePicker` |
| `param.CalendarDateRange` | `pn.widgets.DateRangePicker` | `pmui.DateRangePicker` |

## Containers

| Param Type | Panel Widget | pmui Widget |
|---|---|---|
| `param.List` | `pn.widgets.LiteralInput` | `pmui.LiteralInput` |
| `param.Dict` | `pn.widgets.LiteralInput` | `pmui.LiteralInput` |
| `param.Tuple` | `pn.widgets.LiteralInput` | `pmui.LiteralInput` |

## Special

| Param Type | Panel Widget | pmui Widget |
|---|---|---|
| `param.Color` | `pn.widgets.ColorPicker` | `pmui.ColorPicker` |
| `param.DataFrame` | `pn.widgets.Tabulator` | `pn.widgets.Tabulator` |
| `param.Array` | `pn.widgets.ArrayInput` | — |
| `param.ClassSelector` | `pn.widgets.LiteralInput` | `pmui.LiteralInput` |

## No Widget

These param types have no automatic widget mapping. Use manual widget
construction or `_rename = {"param_name": None}` to exclude from UI.

- `param.Parameter` (generic)
- `param.Callable`
- `param.Action`
- `param.Composite`
- `param.Dynamic`
- `param.Path` / `param.Filename` / `param.Foldername`
