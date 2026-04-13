import sys

from core.csv_importer import import_growth_csv
from core.rule_builder import build_rule
from simulation.registry import Registry
from utils_extensions.utils import extract_celltypes_from_rule


def main():

    if len(sys.argv) < 2:
        print("Usage: python import_rules.py rules.csv")
        return

    path = sys.argv[1]

    registry = Registry()
    registry.load()  

    rules_data = import_growth_csv(path)

    for behaviour, params in rules_data:

        rule = build_rule(behaviour, params)

        new_types = extract_celltypes_from_rule(rule)

        for ct in new_types:
            if ct not in registry.celltype_params:
                registry.add_celltype_params(ct, 50, 10)

        registry.add_rule(rule)

    registry.save()

    print("✅ Import complete!")

if __name__ == "__main__":
    main()