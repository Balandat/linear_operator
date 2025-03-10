# Configuration file for the Sphinx documentation builder.
#
# This file only contains a selection of the most common options. For a full
# list see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Path setup --------------------------------------------------------------

# If extensions (or modules to document with autodoc) are in another directory,
# add these directories to sys.path here. If the directory is relative to the
# documentation root, use os.path.abspath to make it absolute, like shown here.
#
# import os
# import sys
# sys.path.insert(0, os.path.abspath('.'))

import os
import sys
import warnings
from typing import ForwardRef

import jaxtyping
import sphinx_rtd_theme  # noqa


sys.path.append(os.path.abspath(os.path.join(__file__, "..", "..", "..")))

# -- Project information -----------------------------------------------------

project = "linear_operator"
copyright = "2022, Cornellius GP"
author = "Cornellius GP"

# The full version, including alpha/beta/rc tags
try:
    from linear_operator.version import version
except Exception:  # pragma: no cover
    version = "Unknown"  # pragma: no cover

release = version


# -- General configuration ---------------------------------------------------

# Add any Sphinx extension module names here, as strings. They can be
# extensions coming with Sphinx (named 'sphinx.ext.*') or your custom
# ones.
extensions = [
    "myst_parser",  # For adding sections of the README to the docs
    "sphinx.ext.intersphinx",
    "sphinx.ext.coverage",
    "sphinx.ext.mathjax",
    "sphinx.ext.viewcode",
    "sphinx.ext.githubpages",
    "sphinx.ext.autodoc",
    "sphinx_autodoc_typehints",
]

myst_enable_extensions = [
    "amsmath",  # Ensure markdown math from README gets compiled into rst math
    "dollarmath",  # Ensure markdown math from README gets compiled into rst math
    "tasklist",  # Check boxes
]

suppress_warnings = [
    # We use subsections of README in docs, which start with a lower header level
    # than H1, which makes myst_parser complain. This suppresses these warnings.
    "myst.header",
    # The config includes the _process function below, which is "unpickable".
    # This suppresses warnings about caching such values.
    "config.cache",
]

# Add any paths that contain templates here, relative to this directory.
templates_path = ["_templates"]

# List of patterns, relative to source directory, that match files and
# directories to ignore when looking for source files.
# This pattern also affects html_static_path and html_extra_path.
exclude_patterns = []


# -- Options for HTML output -------------------------------------------------

# The theme to use for HTML and HTML Help pages.  See the documentation for
# a list of builtin themes.
#
html_theme = "sphinx_rtd_theme"

# Add any paths that contain custom static files (such as style sheets) here,
# relative to this directory. They are copied after the builtin static files,
# so a file named "default.css" will overwrite the builtin "default.css".
html_static_path = []

# Example configuration for intersphinx: refer to the Python standard library.
intersphinx_mapping = {
    "python": ("https://docs.python.org/3/", None),
    "torch": ("https://pytorch.org/docs/main/", None),
}

# Disable documentation inheritance so as to avoid inheriting
# docstrings in a different format, e.g. when the parent class
# is a PyTorch class.

autodoc_inherit_docstrings = False


# Helper function
# Convert any class (i.e. torch.Tensor, LinearOperator, etc.) into appropriate strings
# For external classes, the format will be e.g. "torch.Tensor"
# For any internal class, the format will be e.g. "~linear_operator.operators.TriangularLinearOperator"
def _convert_internal_and_external_class_to_strings(annotation):
    module = annotation.__module__ + "."
    if module == "linear_operator.operators._linear_operator.":
        module = "~linear_operator."
    elif module.split(".")[0] == "linear_operator":
        module = "~" + module
    elif module == "torch.":
        module = "~torch."
    elif module == "builtins.":
        module = ""
    res = f"{module}{annotation.__name__}"
    return res


# Convert jaxtyping dimensions into strings
def _dim_to_str(dim):
    if isinstance(dim, jaxtyping._array_types._NamedVariadicDim):
        return "..."
    elif isinstance(dim, jaxtyping._array_types._FixedDim):
        res = str(dim.size)
        if dim.broadcastable:
            res = "#" + res
        return res
    elif isinstance(dim, jaxtyping._array_types._SymbolicDim):
        expr = dim.elem
        return f"({expr})"
    elif "jaxtyping" not in str(dim.__class__):  # Probably the case that we have an ellipsis
        return "..."
    else:
        res = str(dim.name)
        if dim.broadcastable:
            res = "#" + res
        return res


# Function to format type hints
def _process(annotation, config):
    """
    A function to convert a type/rtype typehint annotation into a :type:/:rtype: string.
    This function is a bit hacky, and specific to the type annotations we use most frequently.

    This function is recursive.
    """
    # Simple/base case: any string annotation is ready to go
    if type(annotation) == str:
        return annotation

    # Jaxtyping: shaped tensors or linear operator
    elif hasattr(annotation, "__module__") and "jaxtyping" == annotation.__module__:
        cls_annotation = _convert_internal_and_external_class_to_strings(annotation.array_type)
        shape = " x ".join([_dim_to_str(dim) for dim in annotation.dims])
        return f"{cls_annotation} ({shape})"

    # Convert Ellipsis into "..."
    elif annotation == Ellipsis:
        return "..."

    # Convert any class (i.e. torch.Tensor, LinearOperator, etc.) into appropriate strings
    elif hasattr(annotation, "__name__"):
        res = _convert_internal_and_external_class_to_strings(annotation)

    elif str(annotation).startswith("typing.Callable"):
        if len(annotation.__args__) == 2:
            res = f"Callable[{_process(annotation.__args__[0], config)} -> {_process(annotation.__args__[1], config)}]"
        else:
            res = "Callable"

    # Convert any Union[*A*, *B*, *C*] into "*A* or *B* or *C*"
    # Also, convert any Optional[*A*] into "*A*, optional"
    elif str(annotation).startswith("typing.Union"):
        is_optional_str = ""
        args = list(annotation.__args__)
        # Hack: Optional[*A*] are represented internally as Union[*A*, Nonetype]
        # This catches this case
        if args[-1] is type(None):  # noqa E721
            del args[-1]
            is_optional_str = ", optional"
        processed_args = [_process(arg, config) for arg in args]
        res = " or ".join(processed_args) + is_optional_str

    # Convert any Tuple[*A*, *B*] into "(*A*, *B*)"
    elif str(annotation).startswith("typing.Tuple"):
        args = list(annotation.__args__)
        res = "(" + ", ".join(_process(arg, config) for arg in args) + ")"

    # Callable typing annotation
    elif str(annotation).startswith("typing."):
        return str(annotation)[7:]

    # Special cases for forward references.
    # This is brittle, as it only contains case for a select few forward refs
    # All others that aren't caught by this are handled by the final case
    elif isinstance(annotation, ForwardRef):
        res = str(annotation.__forward_arg__)
        if res == "LinearOperator":
            res = "~linear_operator.LinearOperator"
        elif "LinearOperator" in res:
            res = f"~linear_operator.operators.{res}"

    # For everything we didn't catch: use the simplist string representation
    else:
        warnings.warn(f"No rule for {annotation}. Using default resolution...", RuntimeWarning)
        res = str(annotation)

    return res


# Options for typehints

always_document_param_types = False
# typehints_use_rtype = False
typehints_defaults = None  # or "comma"
simplify_optional_unions = False
typehints_formatter = _process

# Taken from https://github.com/pyro-ppl/pyro/blob/dev/docs/source/conf.py#L213
# @jpchen's hack to get rtd builder to install latest pytorch
# See similar line in the install section of .travis.yml
if "READTHEDOCS" in os.environ:
    os.system("pip install torch==2.0+cpu -f https://download.pytorch.org/whl/torch_stable.html")
