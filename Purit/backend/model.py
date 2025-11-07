# # model.py
# import torch
# import torch.nn as nn
# import torch.nn.functional as F

# class SpeakerRecognitionCNN(nn.Module):
#     """
#     A simple 3-layer CNN for speaker classification.
#     Input: (batch, 1, n_mels, time_frames)
#     Output: logits for N speaker classes.
#     """
#     def __init__(self, n_classes, n_mels=64):
#         super().__init__()
#         # Convolutional layers
#         self.conv1 = nn.Conv2d(1, 16, kernel_size=3, padding=1)
#         self.bn1 = nn.BatchNorm2d(16)

#         self.conv2 = nn.Conv2d(16, 32, kernel_size=3, padding=1)
#         self.bn2 = nn.BatchNorm2d(32)

#         self.conv3 = nn.Conv2d(32, 64, kernel_size=3, padding=1)
#         self.bn3 = nn.BatchNorm2d(64)

#         # Pooling and fully connected
#         self.pool = nn.MaxPool2d((2, 2))
#         self.global_pool = nn.AdaptiveAvgPool2d((1, 1))
#         self.fc = nn.Linear(64, n_classes)

#     def forward(self, x):
#         # Input shape: (B, 1, n_mels, T)
#         x = F.relu(self.bn1(self.conv1(x)))
#         x = self.pool(x)
#         x = F.relu(self.bn2(self.conv2(x)))
#         x = self.pool(x)
#         x = F.relu(self.bn3(self.conv3(x)))
#         x = self.pool(x)
#         x = self.global_pool(x)       # shape (B, 64, 1, 1)
#         x = x.view(x.size(0), -1)     # shape (B, 64)
#         logits = self.fc(x)
#         return logits

#     def embed(self, x):
#         """Return 64-D speaker embedding before final classification layer."""
#         x = F.relu(self.bn1(self.conv1(x)))
#         x = self.pool(x)
#         x = F.relu(self.bn2(self.conv2(x)))
#         x = self.pool(x)
#         x = F.relu(self.bn3(self.conv3(x)))
#         x = self.pool(x)
#         x = self.global_pool(x)
#         x = x.view(x.size(0), -1)
#         return x


# model.py
import torch
import torch.nn as nn
import torch.nn.functional as F

class SpeakerRecognitionCNN(nn.Module):
    """
    Simple CNN for speaker classification.
    Input: (batch, 1, n_mels, time_frames)
    """
    def __init__(self, n_classes=2, n_mels=64):
        super().__init__()
        self.n_mels = n_mels
        # Convolutional layers
        self.conv1 = nn.Conv2d(1, 16, kernel_size=3, padding=1)
        self.bn1 = nn.BatchNorm2d(16)

        self.conv2 = nn.Conv2d(16, 32, kernel_size=3, padding=1)
        self.bn2 = nn.BatchNorm2d(32)

        self.conv3 = nn.Conv2d(32, 64, kernel_size=3, padding=1)
        self.bn3 = nn.BatchNorm2d(64)

        # Pooling and fully connected
        self.pool = nn.MaxPool2d((2, 2))
        self.global_pool = nn.AdaptiveAvgPool2d((1, 1))
        self.fc = nn.Linear(64, n_classes)

    def forward(self, x):
        x = F.relu(self.bn1(self.conv1(x)))
        x = self.pool(x)
        x = F.relu(self.bn2(self.conv2(x)))
        x = self.pool(x)
        x = F.relu(self.bn3(self.conv3(x)))
        x = self.pool(x)
        x = self.global_pool(x)       # shape (B, 64, 1, 1)
        x = x.view(x.size(0), -1)     # shape (B, 64)
        logits = self.fc(x)
        return logits

    def embed(self, x):
        """Return 64-D speaker embedding before final classification layer."""
        x = F.relu(self.bn1(self.conv1(x)))
        x = self.pool(x)
        x = F.relu(self.bn2(self.conv2(x)))
        x = self.pool(x)
        x = F.relu(self.bn3(self.conv3(x)))
        x = self.pool(x)
        x = self.global_pool(x)
        x = x.view(x.size(0), -1)
        return x
