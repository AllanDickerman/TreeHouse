import sys
import re
import os.path
from datetime import datetime
import subprocess
import hashlib
import tempfile
import sqlite3

tree_database_file = '../tree_house.db'

def storeTree(newick_string, tree_file, bvbrc_user, file_date):
    #num_tips = len(tree.taxon_namespace)
    (file_path, file_base_name) = os.path.split(tree_file)
    (file_prefix, ext) = os.path.splitext(file_base_name)
    tree_md5 = hashlib.md5(newick_string.encode('utf-8')).hexdigest()
    cursor = tree_db_conn.execute("SELECT rowid from genome_tree where name = ? or md5 = ?", (file_prefix, tree_md5))
    rows = cursor.fetchall()
    if len(rows) > 0:
        return 0, file_prefix # tree appears to exist in database already
    cursor.execute("INSERT INTO genome_tree(md5, name, newick, file_path, file_date, bvbrc_user) VALUES ('{}', '{}', '{}', '{}', '{}', '{}')".format(tree_md5, file_prefix, newick_string, tree_file, file_date, bvbrc_user))
    cursor.execute("SELECT last_insert_rowid() from genome_tree limit(1)")
    tree_id = cursor.fetchone()[0]
    return (tree_id, file_prefix)

def processHomologStats(homologAlignmentStatsFile, tree_id):
    with open(homologAlignmentStatsFile) as homolog_file:
        header = homolog_file.readline()
        for line in homolog_file:
            fields = line.rstrip().split("\t")
            if fields[-1] == "True":
                fam = fields[0]
                mean_squared_freq = fields[2]
                num_pos = fields[3]
                num_seqs = fields[4]
                used_in_tree = fields[7]
                tree_db_conn.execute("INSERT INTO tree_homolog(tree_id, fam, mean_squared_freq, num_pos, num_seqs) values ('{}', '{}', '{}', '{}', '{}')".format(tree_id, fam, mean_squared_freq, num_pos, num_seqs))

def process_local_tree(tree_file):
    print("Processing local tree {}".format(tree_file))
    if not os.path.isfile(tree_file):
        print("Cannot open {}, it is not a file.".format(tree_file))
        return
    F = open(tree_file)
    newick_string = F.read()
    F.close()
    absolute_file_path = os.path.abspath(tree_file)
    file_mtime = os.path.getmtime(absolute_file_path)
    file_date = datetime.fromtimestamp(file_mtime).strftime('%Y-%m-%d %H:%M')
    tree_id, tree_name = storeTree(newick_string, absolute_file_path, bvbrc_user_name, file_date)
    if tree_id == 0:
        print("tree {} appears to exist in database already.".format(tree_name))
        return

    (file_path, file_base_name) = os.path.split(tree_file)
    homologAlignmentStatsFile = file_path + "/detail_files/"+tree_name
    homologAlignmentStatsFile = homologAlignmentStatsFile[:-5]
    homologAlignmentStatsFile += ".homologAlignmentStats.txt"
    print("tree file = "+tree_file)
    print("look for "+homologAlignmentStatsFile)
    if (os.path.isfile(homologAlignmentStatsFile)):
        print("found it")
        processHomologStats(homologAlignmentStatsFile, tree_id);

def process_workspace_tree(file_path):
    print("Processing workspace tree {}".format(file_path))
    tempdirObject = None
    newick_file = None
    data_folder = None
    file_base = None
    m = re.match('^/(.*)@(patricbrc.org|bvbrc).*/(.*)', file_path) 
    if not m:
        raise("cannot parse workspace file path {}".format(file_path))
        return

    bvbrc_user = m.group(1)
    file_base = m.group(3)
    command = ['p3-ls', '-Tald', file_path]
    x = subprocess.run(command, capture_output=True)
    if not x.stdout:
        raise("cannot access workspace file {}".format(file_path))
        return

    dir_parts = x.stdout.decode().rstrip().split(' ')
    file_type = dir_parts[-2]
    if file_type == 'nwk':
        newick_file = dir_parts[-1]
        file_parts = file_path.split("/")
        file_base = file_parts[-2]
        data_folder = "/".join(file_parts[:-1]);
    elif file_type == 'folder':
        data_folder = file_path
        file_base = file_base.lstrip('.') # should have a leading period if it is a job output folder
    elif file_type == 'job_result':
        file_parts = file_path.split("/")
        file_base = file_parts[-1]
        file_parts[-1] = "."+file_base
        data_folder = "/".join(file_parts)

    command = ['p3-ls', '-Tal', data_folder]
    print("\ncommand = "+" ".join(command))
    x = subprocess.run(command, capture_output=True)
    print(x)
    file_date = ''
    for line in x.stdout.decode().split("\n"):
        print("\ndir line: "+line)
        dir_parts = line.rstrip().split()
        print("dir parts: {}: {}".format(len(dir_parts), "|".join(dir_parts)))
        if (dir_parts[-2] == 'nwk'):
            newick_file = dir_parts[-1]
            file_date = "_".join(dir_parts[3:6])
            break


    print("data_folder = "+data_folder) 
    print("newick_file = "+newick_file)
    print("file_base = "+file_base)
    command = ['p3-ls', '-Tal', data_folder+"/detail_files/"+file_base+".homologAlignmentStats.txt"]
    x = subprocess.run(command, capture_output=True)
    print(x.stdout)
    print("we have a workspace file: "+file_path+", belonging to "+bvbrc_user)

    tempdirObject = tempfile.TemporaryDirectory(prefix="tree_import_temp_")
    temp_dir = tempdirObject.name
    #temp_dir = tempfile.mkdtemp(prefix="tree_import_temp_")
    print("temp_dir is {}".format(temp_dir))

    newick_local_file = temp_dir+"/"+newick_file;
    command = ['p3-cp', 'ws:'+data_folder+'/'+newick_file, temp_dir]
    x = subprocess.run(command, capture_output=True)
    print(x.stdout)
    print("command = "+" ".join(command))
    os.mkdir(temp_dir+"/detail_files")
    command = ['p3-cp', 'ws:'+data_folder+"/detail_files/"+file_base+".homologAlignmentStats.txt", temp_dir+'/detail_files/']
    print("command = "+" ".join(command))
    x = subprocess.run(command, capture_output=True)
    print(x.stdout)
    print("data copied to temp_dir {}".format(temp_dir))
    if not os.path.isfile(newick_local_file):
        print("Cannot open {}, it is not a file.".format(newick_local_file))
        return
    with open(newick_local_file) as F:
        newick_string = F.read()
    tree_id, tree_name = storeTree(newick_string, file_path, bvbrc_user, file_date)
    if tree_id == 0:
        print("tree {} appears to exist in database already.".format(tree_name))
        return
    homologAlignmentStatsFile = temp_dir +"/detail_files/"+file_base+".homologAlignmentStats.txt"
    print("look for "+homologAlignmentStatsFile)
    if (os.path.isfile(homologAlignmentStatsFile)):
        print("found it")
        processHomologStats(homologAlignmentStatsFile, tree_id);

x = subprocess.run("p3-whoami", capture_output=True)
m = re.search("PATRIC user (?P<username>\w+)", str(x.stdout))
bvbrc_user_name = m.group('username')
tree_files = sys.argv[1:]
print("argv[0] = "+sys.argv[0])
print("trees to analyze are: "+", ".join(tree_files))
tree_db_conn = sqlite3.connect(tree_database_file)

for file_path in tree_files:
    print("now try file {}".format(file_path))
    if re.match('/.*@(patricbrc.org|bvbrc).*/', file_path):
        process_workspace_tree(file_path)
    else:
        process_local_tree(file_path)


tree_db_conn.commit()
print("Records created successfully")
tree_db_conn.close()

