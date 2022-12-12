import sys
import re
import json
import sqlite3
import subprocess
# output a tree in JSON/newick format

tree_database_file = '../tree_house.db'

def getGenomeNamesViaAPI(genome_ids):
    genome_data = {}
    command = ['p3-get-genome-data', '--nohead', '-a', 'genome_name']
    proc = subprocess.Popen(command, shell=False, encoding='UTF-8', stdin=subprocess.PIPE, stdout=subprocess.PIPE)
    for gid in genome_ids:
        proc.stdin.write(gid+'\n')
    proc.stdin.close() 
    get_genome_data_stdout = proc.stdout.read()
    for line in get_genome_data_stdout.split("\n"):
        if len(line) < 8:
            break
        (genome_id, genome_name) = line.rstrip().split("\t")
        genome_data[genome_id] = genome_name
    return genome_data

def output_tree(tree_id, taxon_id):
    tree_cursor.execute("SELECT newick from genome_tree where rowid = ?", (tree_id,))
    (newick,) = tree_cursor.fetchone();
    
    tree_cursor.execute("SELECT newick from arranged_tree where tree_id = ?", (tree_id,))
    arranged_newick = tree_cursor.fetchone();
    if arranged_newick:
        print("got arranged version of tree")
        newick = arranged_newick[0]

    genome_ids = re.findall("[(,]([^():,]*)[:),]", newick)
    print("got genome ids:\n"+", ".join(genome_ids)+"\n")
    genome_names = getGenomeNamesViaAPI(genome_ids);

    tree_cursor.execute("SELECT name, rank from ncbi_taxon where taxon_id = ?", (taxon_id,))
    (taxon_name, rank) = tree_cursor.fetchone()

    data_object = { 'info' : { 'count': len(genome_ids), 'taxon_name': taxon_name, 'taxon_rank': rank},
            'labels': genome_names,
            'tree': newick
            }

    outfile = "{}_{}_tree.json".format(taxon_name, taxon_id)
    outfile.replace(" ", "_")
    F = open(outfile, 'w')
    print("writing data to "+outfile)
    json.dump(data_object, F, indent=4)

x = subprocess.run("p3-whoami", capture_output=True)
m = re.search("PATRIC user (?P<username>\w+)", str(x.stdout))
bvbrc_user_name = m.group('username')
tree_db_conn = sqlite3.connect(tree_database_file)
tree_cursor = tree_db_conn.execute("SELECT tree_id, taxon_id from flagged_tree_taxon")
tree_taxon_pair = tree_cursor.fetchall()

for pair in tree_taxon_pair:
    tree_id = pair[0]
    taxon_id = pair[1]
    print("tree taxon pair: {} {}".format(pair[0], pair[1]))
    output_tree(tree_id, taxon_id)

tree_db_conn.close()
