# -*- coding: utf-8 -*-
"""Baseline_0.92307.ipynb

Automatically generated by Colaboratory.

Original file is located at
    https://colab.research.google.com/drive/1QRQU9jD_HqJG0Jm0X9WOpMe1txm3isDV
"""

import pandas as pd
import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from torch.optim.lr_scheduler import CosineAnnealingLR
import torch.nn.functional as F
from torchvision import models, transforms
from torch.utils.data import DataLoader, Dataset
from PIL import Image
from sklearn.ensemble import IsolationForest
from tqdm import tqdm
import random
import os

import os
os.environ["CUDA_DEVICE_ORDER"]="PCI_BUS_ID"
os.environ["CUDA_VISIBLE_DEVICES"] = "1"

# GPU 사용 설정
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

from google.colab import drive
drive.mount('/content/gdrive')

def seed_everything(seed):
    random.seed(seed)
    os.environ['PYTHONHASHSEED'] = str(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed(seed)
    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.benchmark = False

seed_everything(41) # Seed 고정

"""Data Load

학습에 필요한 데이터를 불러오고, 전처리를 진행합니다.
"""

# 데이터 로딩 클래스 정의
class CustomDataset(Dataset):
    def __init__(self, csv_file, transform=None):
        """
        Args:
            csv_file (string): csv 파일의 경로.
            transform (callable, optional): 샘플에 적용될 Optional transform.
        """
        self.df = pd.read_csv(csv_file)
        self.transform = transform

    def __len__(self):
        return len(self.df)

    def __getitem__(self, idx):
        img_path = self.df['img_path'].iloc[idx]
        image = Image.open("/content/gdrive/My Drive/Colab_Data/semiconductor_anomaly" + img_path[1:])
        if self.transform:
            image = self.transform(image)
        target = torch.tensor([0.]).float()
        return image,target

# 이미지 전처리 및 임베딩
transform = transforms.Compose([
    # 224,224
    transforms.Resize((224, 224)),
    transforms.ToTensor(),
    transforms.RandomHorizontalFlip(p=0.5),
    transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
])

train_data = CustomDataset(csv_file='/content/gdrive/My Drive/Colab_Data/semiconductor_anomaly/train.csv', transform=transform)
train_loader = DataLoader(train_data, batch_size=16, shuffle=False)

model = models.resnet18(pretrained=True)
model.fc = nn.Linear(512, 1, bias=True)
model = model.to(device)

criterion = nn.BCEWithLogitsLoss()
optimizer = optim.Adam(model.parameters(), lr=0.0005)
scheduler = CosineAnnealingLR(optimizer, T_max=100, eta_min=0.00001)

def train(model, train_loader, criterion, optimizer, scheduler, device, num_epochs):
    for epoch in range(num_epochs):
        model.train()
        running_loss = 0.0
        running_corrects = 0
        total = 0

        for images, labels in train_loader:
            images = images.to(device)
            labels = labels.to(device)

            outputs = model(images)
            loss = criterion(outputs, labels.view(-1, 1))

            optimizer.zero_grad()
            loss.backward()
            optimizer.step()

            running_loss += loss.item()
            predictions = (torch.sigmoid(outputs) > 0.5).float()
            running_corrects += torch.sum(predictions == labels.view(-1, 1)).item()
            total += labels.size(0)

        scheduler.step()

        epoch_loss = running_loss / len(train_loader)
        epoch_acc = running_corrects / total

        print(f'Epoch {epoch+1}/{num_epochs}, Loss: {epoch_loss:.4f}, Accuracy: {epoch_acc:.4f}')

train(model, train_loader, criterion, optimizer, scheduler, device, num_epochs=20)

# 사전 학습된 모델 로드
model.eval()  # 추론 모드로 설정

# 특성 추출을 위한 모델의 마지막 레이어 수정
model = torch.nn.Sequential(*(list(model.children())[:-1]))

model.to(device)

# 이미지를 임베딩 벡터로 변환
def get_embeddings(dataloader, model):
    embeddings = []
    with torch.no_grad():
        for images, _ in tqdm(dataloader):
            images = images.to(device)
            emb = model(images)
            embeddings.append(emb.cpu().numpy().squeeze())
    return np.concatenate(embeddings, axis=0)

train_embeddings = get_embeddings(train_loader, model)

# 테스트 데이터에 대해 이상 탐지 수행
test_data = CustomDataset(csv_file='/content/gdrive/My Drive/Colab_Data/semiconductor_anomaly/test.csv', transform=transform)
test_loader = DataLoader(test_data, batch_size=16, shuffle=False)

test_embeddings = get_embeddings(test_loader, model)

from pyod.models.abod import ABOD

clf_name = 'ABOD'
abod = ABOD(n_neighbors=5)
abod.fit(train_embeddings)

abod_test_pred = abod.predict(test_embeddings)

print(abod_test_pred)

submit = pd.read_csv('/content/gdrive/My Drive/Colab_Data/semiconductor_anomaly/sample_submission.csv')
submit['label'] = abod_test_pred
submit.to_csv('/content/gdrive/My Drive/Colab_Data/'+'ABOD_result.csv', index= None)
submit.head()
=======================================================================================================

from pyod.models.kde import KDE

clf_name = "KDE"
kde = KDE(bandwidth=0.6)
kde.fit(train_embeddings)

kde_test_pred = kde.predict(test_embeddings)

submit = pd.read_csv('/content/gdrive/My Drive/Colab_Data/semiconductor_anomaly/sample_submission.csv')
submit['label'] = kde_test_pred
submit.to_csv('/content/gdrive/My Drive/Colab_Data/'+'KDE_result.csv', index= None)
submit.head()
print(kde_test_pred)

8pred_label = []
for i in range(len(kde_test_pred)):
  if kde_test_pred[i] == abod_test_pred[i]:
    pred_label.append(kde_test_pred[i])
  else:
    pred_label.append(0)

submit = pd.read_csv('/content/gdrive/My Drive/Colab_Data/semiconductor_anomaly/sample_submission.csv')
submit['label'] = pred_label
submit.to_csv('/content/gdrive/My Drive/Colab_Data/'+'Mix_KDE_ABOD_result.csv', index= None)
print(pred_label)