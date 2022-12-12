import sys
import re
import subprocess
import sqlite3
import dendropy
# goal is to characterize which taxa are prominent in the genomes in a tree
# and to calculate average genome-genome distance within prominent taxa and overall
max_prominent_taxa = 1 # up to this many taxa will be characterized

tree_database_file = '../tree_house.db'

def getTaxaForGenomesViaAPI(tree):
    genome_taxa = {}
    command = ['p3-get-genome-data', '--nohead', '-a', 'taxon_lineage_names']
    proc = subprocess.Popen(command, shell=False, encoding='UTF-8', stdin=subprocess.PIPE, stdout=subprocess.PIPE)
    for tip in tree.taxon_namespace:
        proc.stdin.write(tip.label+'\n')
    proc.stdin.close() 
    get_genome_data_stdout = proc.stdout.read()
    for line in get_genome_data_stdout.split("\n"):
        if len(line) < 8:
            break
        (genome_id, lineage_str) = line.rstrip().split("\t")
        #print(genome_id+"^\t^"+lineage_str+"\n")
        lineage_list = lineage_str.split("::")
        genome_taxa[genome_id] = lineage_list
    return genome_taxa

def analyzeTreeTaxa(tree_id, newick_string, taxon_parent):
    tree = dendropy.Tree.get(
            data=newick_string,
            schema="newick") # create new dendropy tree object
    taxon_count = {}
    genome_lineage = {}
    num_tips = len(tree.taxon_namespace)
    for taxon_object in tree.taxon_namespace:
        genome_id = taxon_object.label
        genome_lineage[genome_id] = set()
        taxon = re.sub("\.\d+$", "", genome_id)
        while taxon:
            genome_lineage[genome_id].add(taxon)
            if taxon not in taxon_count:
                taxon_count[taxon] = 0
            taxon_count[taxon] = taxon_count[taxon]+1
            if taxon not in taxon_parent:
                tree_cursor.execute("SELECT parent_id from ncbi_taxon where taxon_id = ?", (taxon,))
                row = tree_cursor.fetchone();
                if row:
                    parent = row[0]
                    if parent:
                        taxon_parent[taxon] = parent;
            if taxon in taxon_parent:
                parent = taxon_parent[taxon]
                if parent == taxon:
                    taxon = None
                else:
                    taxon = taxon_parent[taxon]
            else:
                taxon = None
    print("num_taxa for tree {}: {}".format(tree_id, len(taxon_count)))

    overall_dist = 0
    overall_pair_count = 0
    taxon_dist = {}
    taxon_pair_count = {}
    pdc = tree.phylogenetic_distance_matrix()
#print("got phylogenetic distance matrix, class={}".format(type(pdc)))
    for i, t1 in enumerate(tree.taxon_namespace[:-1]):
        for t2 in tree.taxon_namespace[i+1:]:
            #print("Distance between '%s' and '%s': %s" % (t1.label, t2.label, pdc(t1, t2)))
            overall_dist += pdc(t1, t2)
            overall_pair_count += 1
            for taxon in genome_lineage[t1.label] & genome_lineage[t2.label]:
                if taxon not in taxon_dist:
                    taxon_dist[taxon] = 0
                taxon_dist[taxon] += pdc(t1,t2)
    mean_dist = overall_dist/(num_tips*(num_tips-1))/2
    print("num_tips = {}, average_dist = {:.5f}".format(num_tips, mean_dist))
    cursor = tree_db_conn.execute("UPDATE genome_tree SET mean_dist = ?, num_tips = ? where rowid = ?", (mean_dist, num_tips, tree_id))

    for taxon in taxon_dist:
        n_choose2 = taxon_count[taxon]*(taxon_count[taxon]-1)/2
        #n_choose2 = prominent_taxon_pair_count[taxon]
        mean_dist = taxon_dist[taxon]/n_choose2
        cursor.execute("INSERT INTO tree_taxon(tree_id, taxon_id, num_tips, mean_dist, eclipsed) VALUES ('{}', '{}', {}, {:.6f}, FALSE)".format(tree_id, taxon, taxon_count[taxon], mean_dist))
        print("\ttaxon {} count={} mean_dist={:.5f}".format(taxon, taxon_count[taxon], mean_dist))
    for taxon in taxon_count:
        if taxon in taxon_parent:
            parent = taxon_parent[taxon]
            if (parent in taxon_count) and (taxon_count[parent] == taxon_count[taxon]):
                cursor.execute("UPDATE tree_taxon SET eclipsed = TRUE where tree_id = ? and taxon_id = ?", (tree_id, parent));

x = subprocess.run("p3-whoami", capture_output=True)
m = re.search("PATRIC user (?P<username>\w+)", str(x.stdout))
bvbrc_user_name = m.group('username')
tree_db_conn = sqlite3.connect(tree_database_file)
tree_cursor = tree_db_conn.execute("SELECT rowid, newick from genome_tree WHERE mean_dist is null")
raw_tree={}
for row in tree_cursor.fetchall():
    tree_id = row[0]
    newick = row[1]
    raw_tree[tree_id] = newick

taxon_parent = {}
#taxon_parent = get_all_taxon_parents(raw_trees, taxon_db_conn)
for tree_id in raw_tree:
    tree_cursor.execute("delete from tree_taxon where tree_id = ?", (tree_id,))
    analyzeTreeTaxa(tree_id, raw_tree[tree_id], taxon_parent)
    print(" size of taxon_parent is {}".format(len(taxon_parent)))

tree_db_conn.commit()
print("Records created successfully")
tree_db_conn.close()
