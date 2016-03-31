### Author: Edward Huang

from collections import OrderedDict
import file_operations
import math
import operator
import sys

### This script opens the embedding data and performs drug/pathway analysis.
### We first translate the rows to the right genes and pathways, given by the
### file gene_pathway_id.txt. For each drug-pathway pair, we find a score.
### This score is given by the summation of the top 5 most important genes
### for a drug, taking the cosine similarity between the pathway and the
### gene vectors in the embedding file, multiplied by the correlation between
### the gene and drug response for the drug.

# Writes out to file the top drug-pathway pairs with score equal to the inverse
# of their overall ranking. 
def write_inverse_rankings(subfolder, filename):   
    brd_drug_to_name_dct = file_operations.get_brd_drug_to_name_dct()

    # print 'Taking out top 20 global pathways'
    # top_global_pathways = file_operations.get_top_global_pathways()[:20]

    drug_path_dct = {}
    f = open(subfolder + filename, 'r')
    for i, line in enumerate(f):
        # Skip header lines.
        if i < 2:
            continue
        line = line.strip().split('\t')
        assert len(line) == 3
        drug, path, score = line
        # if path in top_global_pathways:
        #     continue
        drug_path_dct[(drug, path)] = float(score)
    f.close()

    # Sort ppi dictionary by value.
    ranked_drug_path_dct = {}
    drug_path_dct = sorted(drug_path_dct.items(), key=operator.itemgetter(1),
        reverse=True)
    for i, ((drug, path), score) in enumerate(drug_path_dct):
        inverse_ranking = (i + 1) / float(len(drug_path_dct))
        ranked_drug_path_dct[(drug, path)] = inverse_ranking

    ranked_drug_path_dct = sorted(ranked_drug_path_dct.items(),
        key=operator.itemgetter(1), reverse=True)

    out = open(subfolder + 'inverse_rankings/' + 'inverse_' + filename, 'w')
    out.write('drug\tpath\tinverse_rank\n')
    for (drug, path), score in ranked_drug_path_dct:
        out.write('%s\t%s\t%g\n' % (brd_drug_to_name_dct[drug], path, score))
    out.close()

# Computes cosine similarity between two vectors.
def cosine_similarity(v1, v2):
    "compute cosine similarity of v1 to v2: (v1 dot v2)/{||v1||*||v2||)"
    sumxx, sumxy, sumyy = 0, 0, 0
    for i in range(len(v1)):
        x = v1[i]; y = v2[i]
        sumxx += x * x
        sumyy += y * y
        sumxy += x * y
    return sumxy / math.sqrt(sumxx * sumyy)

def find_top_pathways(network, top_k):
    nci_path_dct, nci_genes = file_operations.get_nci_path_dct()
    pathways = nci_path_dct.keys()

    # Find genes and pathways that appear in embedding.
    gene_pathway_lst = file_operations.get_embedding_gene_pathway_lst()

    # Find the top genes for each drug.
    shared_genes, drug_top_genes_dct = file_operations.get_exp_drug_top_genes(
        top_k, gene_pathway_lst)

    # Loop through the files.
    if network == 'ppi':
        # We ran more dimensions for the ppi network.
        dimension_list = [50, 100, 500, 1000, 1500, 2000]
    else:
        dimension_list = [50, 100, 500]
    for dim in map(str, dimension_list):
        for suffix in ['U', 'US']:
            entity_vector_dct = OrderedDict({})

            extension = '%s_0.8.%s' % (dim, suffix)
            if network == 'ppi':
                filename = './data/embedding/ppi_6_net_%s' % extension
            else:
                filename = './data/embedding/%s.network_net_%s' % (network, 
                    extension)
            f = open(filename, 'r')
            for i, line in enumerate(f):
                # There should be the same number of rows in the embedding files
                # as the mapping file.
                entity = gene_pathway_lst[i]
                # Skip genes and pathways we have not previously used.
                if entity not in shared_genes and entity not in pathways:
                    continue
                # Convert lines to floats.
                entity_vector_dct[entity] = map(float, line.split())
            f.close()

            # Calculate the score for each drug-pathway pair.
            score_dct = {}
            for drug in drug_top_genes_dct:
                gene_p_val_dct = drug_top_genes_dct[drug]

                # Get the cosine similarity between each pathway vector and gene
                # vector.
                for pathway in pathways:
                    pathway_vec = entity_vector_dct[pathway]
                    # Have a dictionary for cosine similarity and dictionary for
                    # gene-drug correlation.
                    cosine_dct = {}
                    for gene in gene_p_val_dct:
                        gene_vec = entity_vector_dct[gene]
                        # Compute cosine similarity between pathway and gene.
                        cos = cosine_similarity(pathway_vec, gene_vec)
                        cosine_dct[gene] = cos
                    # Normalize the cosine similarity scores.
                    sum_cos_scores = sum(cosine_dct.values())
                    # for gene in cosine_dct:
                    #     cosine_dct[gene] = cosine_dct[gene] / sum_cos_scores
                    # Initialize the score.
                    drug_path_score = 0.0
                    for gene in gene_p_val_dct:
                        # Correlation between gene and drug response.
                        gene_drug_corr = gene_p_val_dct[gene]
                        cos = cosine_dct[gene]
                        drug_path_score += cos * gene_drug_corr
                    score_dct[(drug, pathway)] = drug_path_score

            # Sort the score dictionary, and write to file.
            score_dct = sorted(score_dct.items(), key=operator.itemgetter(1),
                reverse=True)
            
            subfolder = './results/embedding/'
            out_fname = '%s_top_pathways_%s_top_%d.txt' % (network, extension,
                top_k)
            out = open(subfolder + out_fname, 'w')
            out.write('filler\ndrug\tpath\tscore\n')
            for (drug, pathway), score in score_dct:
                out.write('%s\t%s\t%f\n' % (drug, pathway, score))
            out.close()

            write_inverse_rankings(subfolder, out_fname)

if __name__ == '__main__':
    if (len(sys.argv) != 3):
        print "Usage: " + sys.argv[0] + " ppi/genetic/literome/sequence top_k"
        exit(1)
    network = sys.argv[1]
    top_k = int(sys.argv[2])
    assert network in ['ppi', 'genetic', 'literome', 'sequence']
    
    find_top_pathways(network, top_k)
