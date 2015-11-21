/**
   Utility for converting a tree in a Nexson file to a Taxonomy object.

   Warning - this code is preliminary, and very brittle.  If you feed
   it something that's not valid Nexson HBF 1.2, you'll get a null
   pointer or class cast exception.
*/


package org.opentreeoflife.taxa;

import java.util.Map;
import java.util.HashMap;
import java.util.List;
import java.util.ArrayList;
import java.io.BufferedReader;
import java.io.IOException;

import org.json.simple.JSONObject; 
import org.json.simple.parser.JSONParser; 
import org.json.simple.parser.ParseException;



public class Nexson {

    // json is what the JSON parser returned for the whole file.
    //  looks like {"nexml": {..., "treesById": {...}, ...}}
    // return value is a set of subnodes of that.
    public static Map<String, JSONObject> getTrees(Object json) {
        JSONObject obj = (JSONObject)json;
        JSONObject nexmlContent = (JSONObject)(obj.get("nexml"));
        JSONObject treesById = (JSONObject)(nexmlContent.get("treesById"));
        /* treesById is {"trees1": {
                                    "@otus": "otus1", 
                                    "^ot:treeElementOrder": ["tree1"], 
                                    "treeById": {
                                                 "tree1": { ...} ...} ...} ...}
        */
        Map<String, JSONObject> result = new HashMap<String, JSONObject>();
        for (Object treeses : treesById.values()) {
            JSONObject trees = (JSONObject)(((JSONObject)treeses).get("treeById"));
            for (Object id : trees.keySet()) {
                result.put((String)id, (JSONObject)(trees.get(id)));
            }
        }
        return result;
    }

    public static Map<String, JSONObject> getOtus(Object json) {
        JSONObject obj = (JSONObject)json;
        JSONObject nexmlContent = (JSONObject)(obj.get("nexml"));
        JSONObject otusById = (JSONObject)(nexmlContent.get("otusById"));
        Map<String, JSONObject> result = new HashMap<String, JSONObject>();
        for (Object otuses : otusById.values()) {
            JSONObject otus = (JSONObject)(((JSONObject)otuses).get("otuById"));
            for (Object id : otus.keySet()) {
                result.put((String)id, (JSONObject)(otus.get(id)));
            }
        }
        return result;
    }


    // JSONObject treeson = getTrees(json).get(treeid);

    /* A 'treeson' looks like this:
      {
         "@label": "Bayesian 50% maj-rul consensus", 
         "@xsi:type": "nex:FloatTree", 
         "^ot:branchLengthDescription": "", 
         "^ot:branchLengthMode": "ot:substitutionCount", 
         "^ot:branchLengthTimeUnit": "", 
         "^ot:curatedType": "Bayesian inference ", 
         "^ot:inGroupClade": "node2", 
         "^ot:messages": ..., 
         "^ot:outGroupEdge": "", 
         "^ot:rootNodeId": "node1", 
         "^ot:specifiedRoot": "node1", 
         "^ot:tag": ..., 
         "^ot:unrootedTree": false, 
         "edgeBySourceId": {
                    "node1": {
                              "edge1": {
                                        "@length": 0.05753, 
                                        "@source": "node1", 
                                        "@target": "node2"
                                        }, 
                              "edge84": {
                                         "@length": 0.028765, 
                                         "@source": "node1", 
                                         "@target": "node85"
                                         }
                              }, ...}
         "nodeById": {
              "node1": {
                        "@root": true
                        }, 
              "node10": {}, 
              "node13": {
                         "@otu": "otu1"
                         }, 
              ...
         }
     }
     */
    /*
        {
        "^ot:originalLabel": "Palaemon pacificus", 
        "^ot:ottId": 512598, 
        "^ot:ottTaxonName": "Palaemon pacificus"
        }
    */
    public static SourceTaxonomy importTree(JSONObject treeson, Map<String, JSONObject> otus, String tag) {
        JSONObject nodes = (JSONObject)treeson.get("nodeById");
        JSONObject sources = (JSONObject)treeson.get("edgeBySourceId");
        SourceTaxonomy tax = new SourceTaxonomy();
        tax.setTag(tag);
        Map<String, Taxon> taxa = new HashMap<String, Taxon>(); // maps otu id to Taxon

        // Make a Taxon object for each NeXML node in the tree
        for (Object idObj : nodes.keySet()) {
            String id = (String)idObj;
            // make one Taxon for every node
            Taxon taxon = new Taxon(tax);
            taxon.setId(id);

            // for OTUs (tips), annotate Taxa with OTT id, if present
            JSONObject node = (JSONObject)nodes.get(id);
            Object otuIdObj = node.get("@otu");
            if (otuIdObj != null) {
                String otuId = ((String)otuIdObj);
                JSONObject otu = ((JSONObject)otus.get(otuId));
                Object ottidObj = otu.get("^ot:ottId");
                if (ottidObj != null)
                    taxon.addSourceId(new QualifiedId("ott", ottidObj.toString()));
                Object label = otu.get("^ot:originalLabel");
                if (label != null)
                    taxon.setName((String)label);
            }
            taxa.put(id, taxon);
        }
        for (Object idObj : sources.keySet()) {
            String id = (String)idObj;
            Taxon src = taxa.get(id);
            for (Object edgeObj : ((JSONObject)sources.get(id)).values()) {
                String targetOtuId = ((String)(((JSONObject)edgeObj).get("@target")));
                src.addChild(taxa.get(targetOtuId));
            }
        }
        String rootid = (String)treeson.get("^ot:rootNodeId");
        if (rootid != null && rootid.length() == 0) rootid = null;

        String specid = (String)treeson.get("^ot:specifiedRoot");
        if (specid != null && specid.length() == 0) specid = null;
        if (specid != null && rootid != null && !specid.equals(rootid))
            System.out.format("** Specified root %s not= represented root %s - rerooting NYI\n",
                              specid, rootid);

        if (rootid != null) {
            Taxon node = tax.lookupId(rootid);
            if (node != null)
                tax.addRoot(node);
        } else
            System.out.format("** Root node %s not found in %s\n", rootid, tag);

        return tax;
    }

    public static Object load(String path) throws IOException {
		BufferedReader fr = Taxonomy.fileReader(path);
		JSONParser parser = new JSONParser();
		try {
			return parser.parse(fr);
		} catch (ParseException e) {
			System.err.println(e);
            return null;
		}
    }

}
