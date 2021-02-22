#!/usr/bin/env python3
"""
CLI utility that visualises corporate structure and quantity of land ownership.
"""
import argparse
import collections
import csv
from typing import Dict, IO, Iterator, List, Mapping, NamedTuple, Optional, Tuple, Type


class Company:
    __slots__ = ("_parent_id", "id", "name", "children_ids")

    def __init__(
        self,
        id: str,
        parent_id: Optional[str] = None,
        name: Optional[str] = None,
        children_ids: Optional[List[str]] = None,
    ):
        self.id = id
        self.parent_id = parent_id
        self.name = name
        self.children_ids = [] if children_ids is None else children_ids

    @property
    def parent_id(self):
        return self._parent_id

    @parent_id.setter
    def parent_id(self, new_id):
        # This setter is here to guard against "" being set as parent_id.
        # Assumption: ""/None means this company is a top-level parent itself.
        self._parent_id = None if not new_id else new_id


def get_company_relations(data_file: IO) -> Dict[str, Company]:
    """
    Read company_relations data and generate a mapping:
    {company_id: Company}

    Assumption: a child always has at most one parent, while a parent can have
    any number of children.
    Assumption: a parent of "" indicates no parent, i.e. a top-level company.
    """
    result = {}
    company_relation_type = collections.namedtuple(
        "company_relation", "company_id,name,parent"
    )

    # Discard header line. Pass the primed file to read_csv.
    next(data_file)
    for record in read_csv(data_file, company_relation_type):
        # Records may refer to a parent which we haven't seen yet.
        try:
            parent = result[record.parent]
        except KeyError:
            # Create new Company instance if we haven't seen this parent yet.
            # We can't know its name or parent yet. We'll update those later.
            # Note: only do this for an actual parent (i.e. parent ID is non-empty).
            if record.parent:
                result[record.parent] = Company(
                    id=record.parent, children_ids=[record.company_id]
                )
        else:
            # Update existing instance if a child has already referenced it previously.
            parent.children_ids.append(record.company_id)

        # Similarly the current record may be a parent from the above except-statement.
        try:
            company = result[record.company_id]
        except KeyError:
            # Create new Company instance for the current record.
            result[record.company_id] = Company(
                id=record.company_id, name=record.name, parent_id=record.parent
            )
        else:
            # Update an existing record (a company that was referred to as a parent previously).
            company.name = record.name
            company.parent_id = record.parent

    return result


def get_land_ownership(data_file: IO) -> Dict[str, List[str]]:
    """
    Read land_ownership data and generate a mapping:
    {company_id: [land_id, ...]}
    """
    result = collections.defaultdict(list)
    company_land_type = collections.namedtuple("company_land", "land_id,company_id")

    # Discard header line. Pass the primed file to read_csv.
    next(data_file)
    for record in read_csv(data_file, company_land_type):
        result[record.company_id].append(record.land_id)

    return result


def read_csv(file: IO, structure: Type[NamedTuple]) -> Iterator[NamedTuple]:
    """Read open CSV file into a generator of named tuples."""
    reader = csv.reader(file)
    return (structure(*line) for line in reader)


def parse_args(argv: List[str]) -> argparse.Namespace:
    """
    Parse command line arguments.
    Raises SystemError if the input does not match supported arguments.
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("company_id")
    parser.add_argument("--from_root", dest="from_", action="store_const", const="root")

    return parser.parse_args(argv)


def get_root_company_id(company_id: str, companies: Mapping[str, Company]) -> str:
    """
    Get the top-level parent in the company tree for a given child company_id.
    If the company has no parents, then the original company_id is returned.
    """
    company = companies[company_id]

    if company.parent_id is not None:
        return get_root_company_id(company.parent_id, companies)
    else:
        return company_id


def format_tree(
    tree: Mapping[str, Company],
    company_land: Mapping[str, List[str]],
    root_company_id: str,
    target_company_id: str,
) -> str:
    """
    Format a company tree for output. Use `root_company_id` as the top of the tree.
    Stop expanding the tree at `target_company_id` (not implemented).
    """
    return _format_node(tree, company_land, root_company_id, target_company_id)[0]


def _format_node(
    tree: Mapping[str, Company],
    company_land: Mapping[str, List[str]],
    root_company_id: str,
    target_company_id: str,
    level: int = 0,
) -> Tuple[str, int]:
    output = ""
    total_parcels = len(company_land.get(root_company_id, []))
    company = tree[root_company_id]

    for child_id in company.children_ids:
        child_output, child_parcels = _format_node(
            tree, company_land, child_id, target_company_id, level + 1
        )
        output += child_output
        total_parcels += child_parcels

    if level:
        indent = level * "| " + "- "
    else:
        indent = ""

    line = (
        f"{indent}{company.id}; {company.name}; owner of {total_parcels} land parcels"
    )
    return f"{line}\n{output}", total_parcels


if __name__ == "__main__":
    import sys

    args = parse_args(sys.argv[1:])

    with open("land_ownership.csv") as f:
        company_land = get_land_ownership(f)

    with open("company_relations.csv") as f:
        companies = get_company_relations(f)

    if args.from_ == "root":
        root_company_id = get_root_company_id(args.company_id, companies)
    else:
        root_company_id = args.company_id

    output = format_tree(companies, company_land, root_company_id, args.company_id)
    print(output)
