import torch
from torchvision import datasets, transforms
import torch.nn as nn
from torch.backends import mps
from torch import cuda
from autoencoder import Autoencoder

# Get CPU, GPU or MPS Device for training
device = (
    "cuda"
    if cuda.is_available()
    else "mps"
    if mps.is_available()
    else "cpu"
)

# Data Loading
def load_data():
    transform = transforms.ToTensor()
    mnist_data = datasets.MNIST(root = './data', train = True, download = True, transform = transform)
    data_loader = torch.utils.data.DataLoader(dataset=mnist_data, batch_size = 64, shuffle = True)
    return data_loader

def main():
    data_loader = load_data()
    model = Autoencoder().to(device)
    criterion = nn.MSELoss()
    optimizer = torch.optim.Adam(model.parameters(), lr=1e-3, weight_decay=1e-5)

    num_epochs = 10
    outputs = []
    for epoch in range(num_epochs):
        for (img, _) in data_loader:
            img = img.reshape(-1, 28*28).to(device)
            recon = model(img)
            loss = criterion(recon, img)

            optimizer.zero_grad()
            loss.backward()
            optimizer.step()
        
        print(f'Epoch:{epoch+1}, Loss:{loss.item():.4f}')
        outputs.append((epoch, img, recon))

if __name__ == "__main__":
    main()