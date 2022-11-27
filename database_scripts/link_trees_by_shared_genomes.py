import sys
import re
import os.path
import sqlite3
# goal is to find and record links between trees in form of shared genome ids

tree_database_file = '../tree_house.db'

tree_db_conn = sqlite3.connect(tree_database_file)
cursor = tree_db_conn.cursor()
cursor.execute("SELECT rowid AS tree_id FROM genome_tree WHERE tree_id NOT IN (SELECT tree1_id FROM tree_link WHERE tree1_id = tree2_id)")
records = cursor.fetchall()
unlinked_tree_genomes = {}
for row in records:
    tree_id = row[0]
    unlinked_tree_genomes[tree_id] = None

if len(unlinked_tree_genomes) == 0:
    print("No unlinked trees exist, nothing to do. Exiting.")
    sys.exit(0)

linked_tree_genomes = {}
cursor.execute("SELECT rowid, newick FROM genome_tree")
records = cursor.fetchall()
for row in records:
    tree_id = row[0]
    newick = row[1]
    genome_ids_list = re.findall("[(,](\d+\.\d+)[:)]", newick)
    genome_ids = set(genome_ids_list)
    if tree_id in unlinked_tree_genomes:
        unlinked_tree_genomes[tree_id] = genome_ids
    else:
        linked_tree_genomes[tree_id] = genome_ids

num_links_added = 0
unlinked_id_list = sorted(unlinked_tree_genomes)
for tree1_id in linked_tree_genomes:
    for tree2_id in unlinked_id_list:
        intersect = linked_tree_genomes[tree1_id] & unlinked_tree_genomes[tree2_id]
        if len(intersect):
            shared_genomes = ",".join(sorted(intersect))
            cursor.execute("INSERT INTO TREE_LINK (tree1_id, tree2_id, num_shared, shared_genome_ids) VALUES('{}', '{}', {}, '{}')".format(tree1_id, tree2_id, len(intersect), shared_genomes))
            num_links_added += 1

for i, tree1_id in enumerate(unlinked_id_list[:-1]):
    for tree2_id in unlinked_id_list[i:]: # intentionally include the self comparison, indicates that linking has been performed
        intersect = unlinked_tree_genomes[tree1_id] & unlinked_tree_genomes[tree2_id]
        if len(intersect):
            shared_genomes = ",".join(sorted(intersect))
            cursor.execute("INSERT INTO TREE_LINK (tree1_id, tree2_id, num_shared, shared_genome_ids) VALUES('{}', '{}', {}, '{}')".format(tree1_id, tree2_id, len(intersect), shared_genomes))
            num_links_added += 1
print("num links added = {}".format(num_links_added))
tree_db_conn.commit()
print("Records created successfully")
tree_db_conn.close()
