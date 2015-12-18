from scipy.stats.stats import pearsonr
from scipy.stats import fisher_exact
import operator
from collections import OrderedDict
from selectTopGene import selectTopGenes
import numpy as np
import sys
import random

### Author: Edward Huang
### Find top genes from gene expression, mutation, and LINCS data sets.
### Uses Fisher's test to then use the gene rankings to find most similar
### pathways.

P_THRESHOLD = 0.01
PEARSON_THRESH = 0.1

print 'Extracting NCI pathways...'
path_file = open('./data/nci_pathway.txt', 'r')
pathnames = []
nci_path_dct = {}
for line in path_file:
    line = line.split('\t')
    path_name, path_gene = line[0], line[1][:-2]
    if path_name not in nci_path_dct:
        nci_path_dct[path_name] = [path_gene]
    else:
        nci_path_dct[path_name] += [path_gene]
    if path_name not in pathnames:
        pathnames += [path_name]
path_file.close()

# Get the drug responses from the spreadsheet file.
print 'Extracting drug response values...'
# Keys are drugs, values are lists of drug responses across all patients.
drug_resp_dct = OrderedDict({})
resp_file = open('./data/auc.tsv', 'r')
for i, line in enumerate(resp_file):
    if i == 0:
        continue
    # Each row is one drug's performance on each patient.
    line = line.split()
    drug, resp_line = line[0], line[1:]
    resp_line = [None if resp=='NA' else float(resp) for resp in resp_line]
    drug_resp_dct[drug] = resp_line
resp_file.close()

def write_genes_pathways(data_dct, run):
    print 'Computing Pearson coefficients for ' + run + '...'
    path_out = open('./results/top_pathways_' + run + '.txt', 'w')
    all_top_genes = {}
    for drug in drug_resp_dct:
        drug_top_genes = {}
        drug_resp = drug_resp_dct[drug]
        # List of indices of N/A values in our drug response table.
        NA_indices = [i for i, e in enumerate(drug_resp) if e == None]
        drug_resp = [e for i, e in enumerate(drug_resp) if i not in NA_indices]
        if len(drug_resp) == 0:
            continue
        # Finding the top genes for each drug.
        for gene in data_dct:
            gene_data = data_dct[gene]
            gene_data = [e for i, e in enumerate(gene_data) if i not in NA_indices]
            # Find the pearson coefficient between these two lists.
            pcc, p_value = pearsonr(drug_resp, gene_data)
            if p_value < P_THRESHOLD:
                all_top_genes[(gene, drug)] = p_value
                drug_top_genes[gene] = p_value
        top_genes = sorted(drug_top_genes.items(), key=operator.itemgetter(1))
        # g, d: Gene-Drug Pair.
        top_genes = [gene for gene, pcc in top_genes]
        # Compute the top pathways for each drug.
        top_pathways = {}
        pathway_stats = {}
        for path in nci_path_dct:
            path_genes = set(nci_path_dct[path])
            num_genes = 2 * len(path_genes)
            corr_genes = set(top_genes[:num_genes])
            corr_and_path = len(corr_genes.intersection(path_genes))
            corr_not_path = len(corr_genes.difference(path_genes))
            path_not_corr = len(path_genes.difference(corr_genes))
            neither = len(data_dct) - len(corr_genes.union(path_genes))
            # o_r = odds ratio.
            o_r, p_value = fisher_exact([[corr_and_path, corr_not_path], [path_not_corr, neither]])
            top_pathways[path] = p_value
            pathway_stats[path] = str(corr_and_path) + '\t' + str(corr_not_path) + '\t' + str(path_not_corr) + '\t' + str(neither)
        top_paths = sorted(top_pathways.items(), key=operator.itemgetter(1))
        for path, p_val in top_paths:
            path_out.write(drug + '\t' + path + '\t' + str(p_val) + '\t' + pathway_stats[path] + '\n')
    path_out.close()

    # Sort the top genes by value. Get the top genes.
    gene_out = open('./results/top_genes_' + run + '.txt', 'w')
    print 'Writing top genes for ' + run + '...'
    all_top_genes = sorted(all_top_genes.items(), key=operator.itemgetter(1))
    for (gene, drug), score in all_top_genes:
        gene_out.write(gene + '\t' + drug + '\t' + str(score) + '\n') 
    gene_out.close()

if __name__ == '__main__':
    # Keys are genes, values are lists of gene expression across all patients.
    gene_data_dct = OrderedDict({})
    mut_dct = OrderedDict({})
    genes = []

    print 'Extracting the gene expression vectors...'
    exp_file = open('./data/gene2medProbeExpr.txt', 'r')
    for i, line in enumerate(exp_file):
        if i == 0:
            continue
        line = line.split()
        gene, gene_data_line = line[0], line[1:]
        genes += [gene]
        gene_data_dct[gene] = map(float, gene_data_line)
    exp_file.close()

    print 'Extracting the mutation vectors...'
    mut_file = open('./data/gene2SNPu50SumParse.txt', 'r')
    for i, line in enumerate(mut_file):
        if i == 0:
            continue
        line = line.split()
        gene, mut_line = line[0], line[1:]
        mut_dct[gene] = map(int, mut_line)
    mut_file.close()

    # Write the top pathways for gene expression and mutation.
    write_genes_pathways(gene_data_dct, 'exp')
    write_genes_pathways(mut_dct, 'mut')