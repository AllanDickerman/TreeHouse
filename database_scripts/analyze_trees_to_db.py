import sys
import re
import os.path
from datetime import datetime
import subprocess
import hashlib
import sqlite3
import dendropy
# goal is to characterize which taxa are prominent in the genomes in a tree
# and to calculate average genome-genome distance within prominent taxa and overall
max_prominent_taxa = 10 # up to this many taxa will be characterized
# prominent taxa are ones constituting at least 1/max_prominent_taxa proportion of the genomes on the tree
#  while not including any lower taxa that could qualify as prominent

tree_database_file = '../tree_house.db'

def storeTree(newick_string, tree_file, bvbrc_user):
    #num_tips = len(tree.taxon_namespace)
    (file_path, file_base_name) = os.path.split(tree_file)
    (file_prefix, ext) = os.path.splitext(file_base_name)
    tree_md5 = hashlib.md5(newick_string.encode('utf-8')).hexdigest()
    cursor = tree_db_conn.execute("SELECT rowid from genome_tree where name = ? or md5 = ?", (file_prefix, tree_md5))
    rows = cursor.fetchall()
    if len(rows) > 0:
        return 0, file_prefix # tree appears to exist in database already
    absolute_file_path = os.path.abspath(tree_file)
    file_mtime = os.path.getmtime(absolute_file_path)
    file_date = datetime.fromtimestamp(file_mtime).strftime('%Y-%m-%d %H:%M')
    cursor.execute("INSERT INTO genome_tree(md5, name, newick, file_path, file_date, bvbrc_user) VALUES ('{}', '{}', '{}', '{}', '{}', '{}')".format(tree_md5, file_prefix, newick_string, absolute_file_path, file_date, bvbrc_user))
    cursor.execute("SELECT last_insert_rowid() from genome_tree limit(1)")
    tree_id = cursor.fetchone()[0]
    return (tree_id, file_prefix)

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

def analyzeTreeTaxa(newick_string, tree_id):
    tree = dendropy.Tree.get(
            data=newick_string,
            schema="newick") # create new dendropy tree object
    genome_taxa = getTaxaForGenomesViaAPI(tree)
    taxon_count = {}
    taxon_child = {}
    taxon_genomes = {}
    num_tips = len(tree.taxon_namespace)
    min_for_prominent_taxon = num_tips/max_prominent_taxa
    min_for_prominent_taxon = max(min_for_prominent_taxon, 3)
#print("Need {} genomes per prominent taxon.".format(min_for_prominent_taxon))
    for genome_id in genome_taxa:
        #print("find taxon_child for "+genome_id)
        prev_taxon = None
        for taxon in genome_taxa[genome_id][1:-1]:
            if prev_taxon:
                if prev_taxon not in taxon_child:
                    taxon_child[prev_taxon] = {}
                taxon_child[prev_taxon][taxon]=1
            prev_taxon = taxon
            if taxon not in taxon_count:
                taxon_count[taxon] = 0
            taxon_count[taxon] = taxon_count[taxon]+1
            if taxon not in taxon_genomes:
                taxon_genomes[taxon] = {}
            taxon_genomes[taxon][genome_id] = 1

    print("min_for_prominent_taxon = {}".format(min_for_prominent_taxon))
    for taxa in taxon_count:
        if taxon_count[taxa] >= min_for_prominent_taxon:
            print("count for {} is {}".format(taxa, taxon_count[taxa]))

    prominent_taxa = {}
    prominent_taxon_pair_count = {}
    for taxon in taxon_count:
        if taxon_count[taxon] >= min_for_prominent_taxon:
            #print("consider {} with {} counts.".format(taxon, taxon_count[taxon]))
            eclipsed = False
            if taxon in taxon_child: # why wouldn't it be, but such an occasion arose -- see about not needing this test
                for child in taxon_child[taxon]:
                    if taxon_count[taxon] - taxon_count[child] == 0:
                        eclipsed = True
                        print("\t{} with {} eclipsed by {} with {} counts.".format(taxon, taxon_count[taxon], child, taxon_count[child]))
            if not eclipsed:
                prominent_taxa[taxon] = 0
                prominent_taxon_pair_count[taxon] = 0
                #print("adding prominent taxon "+taxon)
        
    print("prominent taxa: "+", ".join(prominent_taxa))

    overall_dist = 0
    overall_pair_count = 0
    pdc = tree.phylogenetic_distance_matrix()
#print("got phylogenetic distance matrix, class={}".format(type(pdc)))
    for i, t1 in enumerate(tree.taxon_namespace[:-1]):
        for t2 in tree.taxon_namespace[i+1:]:
            #print("Distance between '%s' and '%s': %s" % (t1.label, t2.label, pdc(t1, t2)))
            overall_dist += pdc(t1, t2)
            overall_pair_count += 1
            for taxon in prominent_taxa: # necessary if we have nested prominent taxa
                if taxon in genome_taxa[t1.label] and taxon in genome_taxa[t2.label]:
                    prominent_taxa[taxon] += pdc(t1,t2)
                    prominent_taxon_pair_count[taxon]+=1
    mean_dist = overall_dist/(num_tips*(num_tips-1))/2
    print("num_tips = {}, average_dist = {:.5f}".format(num_tips, mean_dist))
    cursor = tree_db_conn.execute("UPDATE genome_tree SET mean_dist = ?, num_tips = ? where rowid = ?", (mean_dist, num_tips, tree_id))

    for taxon in prominent_taxa:
        n_choose2 = taxon_count[taxon]*(taxon_count[taxon]-1)/2
        #n_choose2 = prominent_taxon_pair_count[taxon]
        mean_dist = prominent_taxa[taxon]/n_choose2
        cursor.execute("INSERT INTO tree_taxon(tree_id, taxon, num_tips, mean_dist) VALUES ('{}', '{}', {}, {:.5f})".format(tree_id, taxon, taxon_count[taxon], mean_dist))
        print("\ttaxon {} count={} mean_dist={:.5f}".format(taxon, taxon_count[taxon], mean_dist))

def process_one_tree(tree_file):
    print("Processing {}".format(tree_file))
    if not os.path.isfile(tree_file):
        print("Cannot open {}, it is not a file.".format(tree_file))
        return
    F = open(tree_file)
    newick_string = F.read()
    F.close()
    tree_id, tree_name = storeTree(newick_string, tree_file, bvbrc_user_name)
    if tree_id == 0:
        print("tree {} appears to exist in database already.".format(tree_name))
        return
    analyzeTreeTaxa(newick_string, tree_id)

    (file_path, file_base_name) = os.path.split(tree_file)
    homologAlignmentStatsFile = file_path + "/detail_files/"+tree_name
    homologAlignmentStatsFile = homologAlignmentStatsFile[:-5]
    homologAlignmentStatsFile += ".homologAlignmentStats.txt"
    print("tree file = "+tree_file)
    print("look for "+homologAlignmentStatsFile)
    if (os.path.isfile(homologAlignmentStatsFile)):
        print("found it")
        with open(homologAlignmentStatsFile) as homolog_file:
            header = homolog_file.readline()
            for line in homolog_file:
                fields = line.rstrip().split("\t")
                if fields[-1] == "True":
                    fam = fields[0]
                    mean_squared_freq = fields[2]
                    num_pos = fields[3]
                    num_seqs = fields[4]
                    tree_db_conn.execute("INSERT INTO tree_homolog(tree_id, fam, mean_squared_freq, num_pos, num_seqs) values ('{}', '{}', '{}', '{}', '{}')".format(tree_id, fam, mean_squared_freq, num_pos, num_seqs))

x = subprocess.run("p3-whoami", capture_output=True)
m = re.search("PATRIC user (?P<username>\w+)", str(x.stdout))
bvbrc_user_name = m.group('username')
tree_files = sys.argv[1:]
print("argv[0] = "+sys.argv[0])
print("trees to analyze are: "+", ".join(tree_files))
tree_db_conn = sqlite3.connect(tree_database_file)
for file in tree_files:
    print("now try file {}".format(file))
    process_one_tree(file)
tree_db_conn.commit()
print("Records created successfully")
tree_db_conn.close()
