# Python 3 server example
import sys
import re
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse
import json
import sqlite3
import subprocess
import os.path
import tempfile
# goal is to write a file with links between trees and a tree descriptor file for Cytoscape

tree_database_file = '../tree_house.db'
hostName = "localhost"
serverPort = 8080
treeData = None

class TreeHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self.end_headers()
        parsed = urlparse(self.path)
        path = parsed.path.lstrip('/')
        print("raw path = "+self.path)
        print("Parsed query = "+parsed.query)
        print("stripped path = "+path)
        if os.path.isfile(path):
            print("found file "+path)
            with open(path) as file_to_serve:
                self.wfile.write(bytes(file_to_serve.read(), "utf-8"))
        elif path == 'get_tree':
            split_query = parsed.query.split("&")
            tree_id = split_query[0]
            use_bvbrc = True
            if len(split_query) > 1:
                if split_query[1] == 'nobvbrc':
                    treeData.set_use_bvbrc(False)
                elif split_query[1] == 'bvbrc':
                    treeData.set_use_bvbrc(True)
            tree_svg = treeData.show_tree(tree_id)
            self.wfile.write(bytes(tree_svg, "utf-8"))
        elif path == 'browse_taxa':
            self.wfile.write(bytes(treeData.generate_taxon_table(parsed.query), "utf-8"))
        elif path == '' or path == 'index' or len(parsed.path) == 0:
            index_string = treeData.generate_tree_table()
            self.wfile.write(bytes(index_string, "utf-8"))
        elif path == 'flag_tree_taxon':
            split_query = parsed.query.split("&")
            tree_id = split_query[0].split('=')[1]
            taxon_id = split_query[1].split('=')[1]
            treeData.flag_tree_taxon(tree_id, taxon_id)
        else:
            self.wfile.write(bytes("<html><head><title>Tree Server Response</title></head>", "utf-8"))
            self.wfile.write(bytes("<body>", "utf-8"))
            self.wfile.write(bytes("<p>Request: %s</p>" % self.path, "utf-8"))
            self.wfile.write(bytes("<p>path: %s</p>" % path, "utf-8"))
            self.wfile.write(bytes("<p>query: %s</p>" % parsed.query, "utf-8"))
            self.wfile.write(bytes("</body></html>", "utf-8"))

    def do_POST(self):
        print("Post raw path = "+self.path)
        if (self.path.startswith("/save_arranged_tree")):
            self.data_string = self.rfile.read(int(self.headers['Content-Length']))
            data = json.loads(self.data_string)
            print("data.tree_id={}, nwk='{}'".format(data['tree_id'], data['nwk']))
            treeData.save_arranged_tree(data['tree_id'], data['nwk'])


        self.send_response(200)
        self.send_header('Access-Control-Allow-Credentials', 'true')
        self.send_header('Access-Control-Allow-Origin', 'http://localhost:8080')
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        self.wfile.write('{"status": "done"}'.encode(encoding='utf_8'))

        return



class TreeData:
    def __init__(self, database_file):
        self.tree_db_conn = sqlite3.connect(database_file)
        self.cur = self.tree_db_conn.cursor()
        self.trees = {}
        self.use_bvbrc = True
        self.cur.execute("SELECT rowid, name, num_tips, mean_dist FROM genome_tree ")
        records = self.cur.fetchall()
        for row in records:
            (row_id, name, num_tips, mean_dist)  = row
            if not mean_dist:
                mean_dist = 0
            self.trees[row_id] = {'name':name, 'num_tips': num_tips, 'mean_dist': mean_dist, 'num_homologs':0, 'arranged':False, 'taxa': {}}
        sys.stderr.write("got trees, num= {}\n".format(len(self.trees)))
        self.cur.execute("SELECT tree_id FROM arranged_tree")
        records = self.cur.fetchall()
        for row in records:
            tree_id  = row[0]
            if tree_id in self.trees:
                self.trees[tree_id]['arranged'] = True
            else:
                print("got a tree_id not in the tree list: "+str(tree_id))
        self.taxa = {}
        self.cur.execute("SELECT tree_id, count(*) FROM tree_homolog GROUP BY tree_id")
        records = self.cur.fetchall()
        for row in records:
            (tree_id, num_homologs)  = row
            self.trees[tree_id]['num_homologs'] = int(num_homologs)
        self.cur.execute("SELECT tree_id, tree_taxon.taxon_id, ncbi_taxon.name, ncbi_taxon.rank, num_tips, mean_dist FROM tree_taxon, ncbi_taxon where ncbi_taxon.taxon_id = tree_taxon.taxon_id and tree_taxon.taxon_id > 2 and not eclipsed order by num_tips desc") 
        records = self.cur.fetchall()
        for row in records:
            (tree_id, taxon_id, taxon_name, taxon_rank, num_tips, mean_dist)  = row
            self.trees[tree_id]['taxa'][taxon_name] = {'num_tips': num_tips, 'mean_dist': mean_dist, 'taxon_id': taxon_id, 'taxon_rank': taxon_rank}
            if taxon_name not in self.taxa:
                self.taxa[taxon_name] = []
            self.taxa[taxon_name].append([tree_id, num_tips, mean_dist])
        
    def generate_tree_table(self):
        retval = "<html><head>\n";
        retval += "<link rel='stylesheet' href='tree_style.css'>\n";
        retval += "</head><body>\n"
        retval += "<h1>Tree List (number of trees = {})</h1>\n".format(len(self.trees))
        retval += "<button  onclick=\"window.location='browse_taxa'\">Browse Taxa</button>\n";
        retval += "<table>\n"
        retval += "<tr><th>ID</th><th>Name (link)</th><th>Num Tips</th><th>Mean Dist</th><th>Num Genes</th><th>Arranged</th></tr>\n";
        for tree_id in sorted(self.trees):
            retval += "<tr><td>{}</td><td class='tree_link' onclick=\"window.location.href='get_tree?{}'\">{}</td><td>{}</td><td>{:.3f}</td>"\
                    .format(tree_id, tree_id, self.trees[tree_id]['name'], self.trees[tree_id]['num_tips'], self.trees[tree_id]['mean_dist'])
            retval += "</td><td>{}</td><td>{}</td></tr>\n".format(self.trees[tree_id]['num_homologs'], self.trees[tree_id]['arranged'])
        retval += "</table></html>\n"
        return retval

    def generate_taxon_table(self, target_taxon=None):
        print("treeData.generate_taxon_table( target_taxon = {})".format(target_taxon))
        retval = "<html><head>\n";
        retval += "<link rel='stylesheet' href='tree_style.css'>\n";
        retval += "</head><body>\n"
        taxon_list = []
        if target_taxon and target_taxon in self.taxa:
            retval += "<button  class='taxon_link' onclick=\"window.location='browse_taxa'\">Browse All Taxa</button>\n"
            taxon_list = [target_taxon]
            retval += "<h1>Trees for Taxon {}</h1>\n".format(target_taxon)
        else:
            taxon_list = sorted(self.taxa)
            retval += "<h1>Taxon List (number of taxa = {})</h1>\n".format(len(self.taxa))
        retval += "<button  onclick=\"window.location='index'\">Browse Trees</button>\n"
        retval += "<table>\n"
        retval += "<tr><td>Taxon Name</td><td>Tree ID</td><td>Taxon <br>Occurrences</td><td>Tips on<br> Tree</td><td>Dist Within<br> Taxon</td><td>Dist on<br> Tree</td></tr>\n"
        for taxon_name in taxon_list:
            trees_for_taxon = self.taxa[taxon_name]
            (tree_id, num_tips, mean_dist) = trees_for_taxon[0]
            retval += "<tr><td rowspan={}>{}</td><td class='tree_link' onclick=\"window.location.href='get_tree?{}'\">{}</td><td>{}</td><td>{}</td><td>{:.4f}</td><td>{:.4f}</td></tr>\n".format(len(trees_for_taxon), taxon_name, tree_id, tree_id, num_tips, self.trees[tree_id]['num_tips'], mean_dist, self.trees[tree_id]['mean_dist'], )
            for row in trees_for_taxon[1:]:
                (tree_id, num_tips, mean_dist) = row
                retval += "<tr><td class='tree_link' onclick=\"window.location.href='get_tree?{}'\">{}</td><td>{}</td><td>{}</td><td>{:.4f}</td><td>{:.4f}</td></tr>\n".format(tree_id, tree_id, num_tips, self.trees[tree_id]['num_tips'], mean_dist, self.trees[tree_id]['mean_dist'])
        retval += "</table></html>\n"
        return retval

    def set_use_bvbrc(self, on_off):
        self.use_bvbrc = on_off
        print("treeData.set_use_bvbrc({})".format(on_off))

    def show_tree(self, tree_id):
        print("tree_data.show_tree(tree_id={})".format(tree_id))
        tree_id = int(tree_id)
        retval = "<html><head>\n"
        retval += "<link rel='stylesheet' href='tree_style.css'>\n"
        retval += "<script type='text/javascript' src='svg_tree.js'></script></head><body>\n"
        if tree_id not in self.trees:
            retval += "Tree {} does not exist in database.</html>\n".format(tree_id)
            return retval
        retval += "<h3>Tree <span id='tree_id'>{}</span> &nbsp; {}</h3>\n".format(tree_id, self.trees[tree_id]['name'])
        retval += "<button onclick=\"window.location='get_tree?{}'\">Next Tree</button> &nbsp; <button  onclick=\"window.location='index'\">Browse Trees</button> &nbsp; <button  class='taxon_link' onclick=\"window.location='browse_taxa'\">Browse Taxa</button> <p>\n".format(tree_id, tree_id+1)
        retval += "<table>\n"
        retval += "<tr><th>Num Tips</th><th>Num Genes</th><th>Mean Dist.</th><th>Arranged</th><tr>\n";
        mean_dist = 'NA'
        if 'mean_dist' in self.trees[tree_id] and self.trees[tree_id]['mean_dist']:
            mean_dist = "{:.3f}".format(self.trees[tree_id]['mean_dist'])
        retval += "<tr><td>{}</td><td>{}</td><td>{}</td><td>{}</td><tr>\n".format(self.trees[tree_id]['num_tips'], self.trees[tree_id]['num_homologs'], mean_dist, self.trees[tree_id]['arranged']) 
        retval += "</table><p>\n"
        if len(self.trees[tree_id]['taxa']):
            retval += "<b>Taxa in Tree {}</b>\n".format(tree_id)
            retval += "<table>\n"
            retval += "<tr><th>{}</th><th>{}</th><th>{}</th><tr>\n".format('Taxon', 'Number', 'Mean Distance')
            for taxon in self.trees[tree_id]['taxa']:
                taxon_data = self.trees[tree_id]['taxa'][taxon]
                retval += "<tr><td class='taxon_link' onclick=\"window.location='browse_taxa?{}'\">{}</td><td>{}</td><td onclick=\"flag_tree_taxon({}, {})\">{:.3f}</td><tr>\n".format(taxon, taxon, taxon_data['num_tips'], tree_id, taxon_data['taxon_id'], taxon_data['mean_dist']) 
            retval += "</table></p>\n"
        else:
            retval += "No taxa are annotated.\n"

        #retval += "<table><td>"
        retval += "<label for='annotation_field_select'>Label field:</label>\n"
        retval += "<select id='annotation_field_select'>\n"
        retval += "</select>\n"
        retval += "&nbsp;";
        retval += "<label for='node_action_select'>Node Action</label>\n"
        retval += "<select id='node_action_select'>\n"
        retval += "<option value='highlight'>Highlight Nodes</option>\n"
        retval += "<option value='swap'>Swap Children</option>\n"
        retval += "<option value='reroot'>Re-root Tree</option>\n"
        retval += "<option value='newick'>Newick Subtree</option>\n"
        retval += "</select>\n"
        retval += "&nbsp;";
        #retval += "</td><td>\n";
        retval += "<label for='global_action_select'>Global Action</label>\n"
        retval += "<select id='global_action_select' onchange='global_action()'>\n";
        retval += "<option value='generate_newick'>Generate Newick</option>\n"
        retval += "<option value='save_arrangement'>Save Arrangement</option>\n"
        #retval += "<option value='generate_json_newick'>Generate Json Newick</option>\n"
        retval += "<option value='order_tree_up'>Order Tree Up</option>\n"
        retval += "<option value='order_tree_down'>Order Tree Down</option>\n"
        retval += "</select>\n"
        #retval += "</td></tr></table>"

        retval += "<div style='width: 800px; height: 600px; overflow-y: scroll;'>\n"
        retval += self.get_tree_as_svg(tree_id)
        retval += "</div>"
        retval += "</html>"
        return retval

    def get_tree_as_svg(self, tree_id):
        print("tree_data.get_tree_as_svg(tree_id={})".format(tree_id))
        tree_id = int(tree_id)
        tree_name = self.trees[tree_id]['name']
        #svgFile = f"tree_web_{tree_name}.svg"
        #if not os.path.exists(svgFile):
        self.cur.execute(f"SELECT name, newick FROM genome_tree where rowid = {tree_id}")
        (tree_name, newick_string) = self.cur.fetchone()
        self.cur.execute(f"SELECT newick FROM arranged_tree where tree_id = {tree_id}")
        (arranged_tree) = self.cur.fetchone();
        if (arranged_tree):
            print("found arranged tree for id {}".format(tree_id))
            newick_string = arranged_tree[0]

        #newickFile = f"tree_web_{tree_name}.nwk"
        #with open(newickFile, 'w') as n:
        #    n.write(newick_string+"\n")
        print(newick_string)
        command=['p3x-reformat-tree', '--output_format', 'svg']
        if (self.use_bvbrc):
            command.extend(('-l', 'genome_id', '-g', 'genome_name,family,order'));
        sys.stderr.write("command = "+" ".join(command)+"\n")
        #return_code = subprocess.call(command, shell=False) 
        proc = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE)
        proc.stdin.write(bytes(newick_string, "utf-8"))
        proc.stdin.close()
        svg_string = proc.stdout.read()
        return svg_string.decode('ASCII')

    def save_arranged_tree(self, tree_id, arranged_nwk):
        print("save_arranged_tree({}, {})".format(tree_id, arranged_nwk[:20]))
        self.cur.execute("SELECT count(*) from arranged_tree WHERE tree_id=?", (tree_id,))
        existing_tree = self.cur.fetchone()[0]
        print("existing tree({})".format(existing_tree))
        if (existing_tree):
            self.cur.execute("UPDATE arranged_tree set newick = ? WHERE tree_id = ?", (arranged_nwk, int(tree_id)))
        else:
            self.cur.execute("INSERT INTO arranged_tree (tree_id, newick) VALUES (?, ?)", (int(tree_id), arranged_nwk))
        self.tree_db_conn.commit()

    def flag_tree_taxon(self, tree_id, taxon_id):
        print("treeData.flag_tree_taxon({}, {})".format(tree_id, taxon_id))
        self.cur.execute("select taxon_id from flagged_tree_taxon where tree_id = ?", (tree_id,))
        existing_taxon = self.cur.fetchone()
        if existing_taxon:
            self.cur.execute("UPDATE flagged_tree_taxon SET taxon_id = ? where tree_id = ?", (int(taxon_id), int(tree_id)))
        else:
            self.cur.execute("INSERT INTO flagged_tree_taxon (tree_id, taxon_id) VALUES (?, ?)", (int(tree_id), taxon_id))


if __name__ == "__main__":        
    webServer = HTTPServer((hostName, serverPort), TreeHandler)
    print("Server started http://%s:%s" % (hostName, serverPort))

    treeData = TreeData(tree_database_file)
    print("Files available:")
    files = os.listdir()
    for f in files:
        if (os.path.isfile(f)):
            print(f"file: {f}")

    try:
        webServer.serve_forever()
    except KeyboardInterrupt:
        webServer.server_close()
        print("Server stopped.")

