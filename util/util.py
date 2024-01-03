"""
File: util.py
Author: Nikhil Sengupta
Created on: November 6, 2023
Last Modified: January 5, 2024
Email: ns214@st-andrews.ac.uk

Description: 
    This file contains utility functions common to all models,
    such as assertions, visualizations of data, etc.

License:
    This code is released under the MIT License
"""

import logging
import matplotlib.pyplot as plt
import numpy as np
import seaborn as sns
from torch import nn
from sklearn.manifold import TSNE
import csv

"""
Visualize the original and reconstructed images
:param originals: The original images
:type originals: torch.Tensor
:param reconstructions: The reconstructed images
:type reconstructions: torch.Tensor
:param dataset: The dataset used
:type dataset: str
:param n: The number of images to visualize
:type n: int
"""
def visualize_comparisons(originals, reconstructions, dataset, num_imgs, results_file):
    logging.info(f"Generating {num_imgs} images...")
    plt.figure(figsize=(20, 4))
    for i in range(num_imgs): # Display original images
        ax = plt.subplot(2, num_imgs, i + 1)
        if dataset in ["mnist", "fashion-mnist", "mnist-corrupted"]:
            plt.imshow(originals[i].reshape(28, 28))
        elif dataset in ["cifar10", "cifar100", "super-tiny-imagenet"]:
            plt.imshow(originals[i].reshape(3, 32, 32).transpose(1, 2, 0))
        else:
            plt.imshow(originals[i].reshape(3, 64, 64).transpose(1, 2, 0))
        ax.get_xaxis().set_visible(False)
        ax.get_yaxis().set_visible(False)

        # Display reconstructed images
        ax = plt.subplot(2, num_imgs, i + 1 + num_imgs)
        if dataset in ["mnist", "fashion-mnist", "mnist-corrupted"]:
            plt.imshow(reconstructions[i].reshape(28, 28))
        elif dataset in ["cifar10", "cifar100", "super-tiny-imagenet"]:
            plt.imshow(reconstructions[i].reshape(3, 32, 32).transpose(1, 2, 0))
        else:
            plt.imshow(reconstructions[i].reshape(3, 64, 64).transpose(1, 2, 0))
        ax.get_xaxis().set_visible(False)
        ax.get_yaxis().set_visible(False)

    # Save the images
    logging.info(f"Saving images to output file...")
    plt.savefig(results_file)

"""
Evaluate the network based on the test data and the predicted data
:param test_data: The test data
:type test_data: torch.Tensor
:param pred_data: The predicted data
:type pred_data: torch.Tensor
:return: The loss and accuracy
:rtype loss: torch.Tensor
:rtype accuracy: torch.Tensor
"""
def evaluate(test_data, pred_data):
    criterion = nn.MSELoss()
    loss = criterion(test_data, pred_data)
    accuracy = 0
    return loss, accuracy

"""
Plot the latent space representation of the model
:param model: The model to plot
:type model: torch.nn.Module
:param loader: The data loader to use
:type loader: torch.utils.data.DataLoader
:param results_file: The file to save the results to
:type results_file: str
"""
def plot_latent_representation(model, loader, dataset, task, results_file):
    points = []
    labels = []

    task_names = {
        "reconstruction": "Reconstruction",
        "anomaly-detection": "Anomaly Detection",
    }

    dataset_names = {
        "mnist": "MNIST",
        "fashion-mnist": "Fashion-MNIST",
        "cifar10": "CIFAR-10",
        "cifar100": "CIFAR-100",
        "super-tiny-imagenet": "Super Tiny ImageNet",
        "tiny-imagenet": "Tiny ImageNet"
    }

    for (img, label) in loader:
        img = img.reshape(-1, model.input_shape[0]).to(model.device)
        proj = model.encoded_representation(img)
        points.append(proj.detach().cpu().numpy())
        labels.append(label.detach().cpu().numpy())

    points = np.concatenate(points, axis=0)
    labels = np.concatenate(labels, axis=0)

    tsne = TSNE(n_components=2, random_state=0)
    tsne_results = tsne.fit_transform(points)

    plt.figure(figsize=(12, 10))
    num_classes = np.unique(labels).size

    # Check for 'dataset' attribute to determine how to access class names
    if hasattr(loader.dataset, 'dataset') and hasattr(loader.dataset.dataset, 'classes'):
        class_names = loader.dataset.dataset.classes
    elif hasattr(loader.dataset, 'classes'):
        class_names = loader.dataset.classes
    else:
        class_names = [str(i) for i in range(num_classes)]

    for i in range(num_classes):
        indices = labels == i
        plt.scatter(tsne_results[indices, 0], tsne_results[indices, 1], label=class_names[i], alpha=0.5)

    plt.title(f"{model.name} Latent Space Representation of the {dataset_names[dataset]} Dataset for {task_names[task]}")
    plt.xlabel("t-SNE Dimension 1")
    plt.ylabel("t-SNE Dimension 2")
    plt.legend()
    plt.savefig(results_file)

"""
Plot the loss distribution of the model
:param model_name: The name of the model
:type model_name: str
:param losses: The losses to plot
:type losses: list
:param dataset: The dataset used
:type dataset: str
:param results_file: The file to save the results to
:type results_file: str
"""
def plot_loss_distribution(model_name, losses, dataset, results_file):
    dataset_names = {
        "mnist": "MNIST",
        "fashion-mnist": "Fashion-MNIST",
        "cifar10": "CIFAR-10",
        "cifar100": "CIFAR-100",
        "super-tiny-imagenet": "Super Tiny ImageNet",
        "tiny-imagenet": "Tiny ImageNet"
    }

    plt.figure(figsize=(10, 6))
    plt.title(f"{model_name} Loss Distribution of Partially Noisy {dataset_names[dataset]} Test Dataset")
    sns.distplot(losses, bins=100, kde=False, color="blue")
    plt.xlabel("Test Loss")
    plt.ylabel("Number of Images")
    plt.savefig(results_file)

"""
Save the results to a CSV file
:param dataset: The dataset used
:type dataset: str
:param phased: Boolean indicating whether the model was monitored in a phased manner
:type phased: bool
:param result_strategy: The result strategy used
:type result_strategy: str
"""
def save_result_data(result_data, results_file):
    with open (results_file, 'a', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(result_data)

"""
Print the header of a stage
:param header: The header to print
:type header: str
"""
def print_header(header):
    result_str = "\n" + header + "\n" + "=" * len(header)
    print(result_str)

"""
Exit the program with an error message of the correct usage
:param msg: The error message to display
:type msg: str
:param parser: The parser to use to print the correct usage
:type parser: argparse.ArgumentParser
"""
def exit_with_error(msg, parser):
    logging.error(msg)
    parser.print_help()
    exit(1)

"""
Assert a condition and log the error if the condition is not met
:param condition: The condition to assert
:type condition: bool
:param msg: The error message to display
:type msg: str
"""
def assert_cond(condition, msg):
    try:
        assert condition, msg
    except AssertionError as e:
        logging.error(e)
        raise e
