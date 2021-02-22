# To run these, simply run pytest from the command line:
# ```
# python3.8 -m virtualenv $dest_dir
# . $dest_dir/bin/activate
# pip install -r requirements_dev.txt
# pytest
# ```
import collections
import io

import pytest

import landtree


@pytest.fixture
def land_ownership_file():
    return io.StringIO("\n".join([
        "land_id,company_id",
        "T100018863440,R590980645905",
        "T100030485625,C498567266942",
        "T10201682101,R590980645905",
    ]))


def test_parse_args__no_opts():
    """
    Unit test: parses company_id from argv.
    Options are optional.
    """
    args = landtree.parse_args(["foo"])

    assert args.company_id == "foo"
    assert args.from_ is None


@pytest.mark.parametrize("argv", (
    ["--from_root", "foo"],
    ["foo", "--from_root"],
))
def test_parse_args__with_opts(argv):
    """
    Unit test: parses company_id and "from" option from argv.
    """
    args = landtree.parse_args(argv)

    print(args)

    assert args.company_id == "foo"
    assert args.from_ == "root"


def test_parse_args__arg_is_non_optional():
    with pytest.raises(SystemExit):
        landtree.parse_args(["--from_root"])


def test_read_csv(land_ownership_file):
    """
    Unit test: reads CSV data from buffer and returns a generator of the provided type.
    If you accidentally feed it the CSV's header line, that will end up in the results too.
    """
    dummy_type = collections.namedtuple("dummy_type", "foo,bar")

    result = landtree.read_csv(land_ownership_file, dummy_type)

    assert next(result) == dummy_type("land_id", "company_id")
    assert next(result) == dummy_type("T100018863440", "R590980645905")
    assert next(result) == dummy_type("T100030485625", "C498567266942")
    assert next(result) == dummy_type("T10201682101", "R590980645905")
    with pytest.raises(StopIteration):
        next(result)


def test_get_land_ownership(land_ownership_file):
    """
    Unit test: produces company -> land index from CSV data in buffer.
    Should discard the header row from the data.
    """
    result = landtree.get_land_ownership(land_ownership_file)

    assert result["R590980645905"] == ["T100018863440", "T10201682101"]
    assert result["C498567266942"] == ["T100030485625"]
    assert result.get("company_id") is None


def test_get_company_relations__no_empty_parents():
    """
    Unit test: produces Company instances from CSV data in buffer.
    Returned value is a mapping company_id => Company instance.
    Should register children with their parents (and vice versa, but that part's easy).
    Should discard the header row from the data.
    """
    company_relations_file = io.StringIO("\n".join([
        "company_id,name,parent",
        "C100517359149,Leseetan Midlands Group Limited,R764915829891",
        "C101307938502,Cheales lesitech Plc,S100240634395",
        "C47634269492,leseetan new group,R764915829891",
    ]))

    result = landtree.get_company_relations(company_relations_file)
    sample = result["C100517359149"]

    assert sample.id == "C100517359149"
    assert sample.name == "Leseetan Midlands Group Limited"
    assert sample.parent_id == "R764915829891"
    assert sample.children_ids == []

    assert result["R764915829891"].name is None
    assert result["R764915829891"].parent_id is None
    assert result["R764915829891"].children_ids == ["C100517359149", "C47634269492"]

    assert result.get("company_id") is None


def test_get_company_relations__top_level_parent_created_directly():
    """
    Bugfix: Top-level companies should have a parent `None`.
    The company_relations dict should not contain any company with ID "" or None.
    """
    company_relations_file = io.StringIO("\n".join([
        "company_id,name,parent",
        "foo,Bar Limited,",
    ]))
    result = landtree.get_company_relations(company_relations_file)

    assert result["foo"].parent_id is None
    assert result.get("") is None  # This was the bug.
    assert result.get(None) is None  # Seems prudent to test for this case too.


def test_get_company_relations__top_level_parent_created_indirectly():
    """
    Bugfix: Parent Company instances that were created due to processing a child record
    would have their parent set to whatever was in the CSV, including "".
    The company_relations dict should not contain any company with ID "" or None.
    """
    company_relations_file = io.StringIO("\n".join([
        "company_id,name,parent",
        "bar,Bar Limited,foo",
        "foo,Foo Limited,",
    ]))
    result = landtree.get_company_relations(company_relations_file)

    assert result["foo"].parent_id is None  # This was the bug.
    assert result.get("") is None  # Can't hurt to test this one again.
    assert result.get(None) is None  # Seems prudent to test for this case too.


@pytest.fixture
def company_relations():
    return {
        "A": landtree.Company(id="A", name="Company A", parent_id=None, children_ids=["B"]),
        "B": landtree.Company(id="B", name="Company B", parent_id="A", children_ids=["C"]),
        "C": landtree.Company(id="C", name="Company C", parent_id="B", children_ids=[]),
        "D": landtree.Company(id="D", name="Company D", parent_id=None, children_ids=["E", "X"]),
        "E": landtree.Company(id="E", name="Company E", parent_id="D", children_ids=["F"]),
        "F": landtree.Company(id="F", name="Company F", parent_id="E", children_ids=[]),
        "X": landtree.Company(id="X", name="Company X", parent_id="D", children_ids=[]),
    }


@pytest.mark.parametrize("company_id, expected", (
    ["C", "A"],
    ["B", "A"],
    ["A", "A"],
    ["F", "D"],
    ["E", "D"],
    ["D", "D"],
))
def test_get_root_company_id(company_id, expected, company_relations):
    """
    Unit test: finds the top-level parent company in a tree.
    Should return the input company_id if company has no parents.
    """
    result = landtree.get_root_company_id(company_id, company_relations)
    assert result == expected


def test_format_tree(company_relations):
    """
    Unit test: formats company data and land ownership data for output.
    Should have root company at the top of output.
    Should not recurse beyond target company.
    """
    company_land = {
        "A": ["v"],
        "C": ["v", "v"],
        "D": ["v", "v", "v", "v"],
        "F": ["v", "v", "v", "v", "v", "v", "v", "v"]
    }
    result = landtree.format_tree(company_relations, company_land, root_company_id="A", target_company_id="C")

    assert result == "\n".join((
        "A; Company A; owner of 3 land parcels",
        "| - B; Company B; owner of 2 land parcels",
        "| | - C; Company C; owner of 2 land parcels",
        "",
    ))

