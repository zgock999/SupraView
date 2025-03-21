"""
RRDBNet アーキテクチャの実装
Real-ESRGANで使用されるネットワークアーキテクチャ

参考元：https://github.com/xinntao/Real-ESRGAN
"""
import math
import torch
import torch.nn as nn
from torch.nn import functional as F


class ResidualDenseBlock(nn.Module):
    """Residual Dense Block."""

    def __init__(self, num_feat=64, num_grow_ch=32):
        super(ResidualDenseBlock, self).__init__()
        self.conv1 = nn.Conv2d(num_feat, num_grow_ch, 3, 1, 1)
        self.conv2 = nn.Conv2d(num_feat + num_grow_ch, num_grow_ch, 3, 1, 1)
        self.conv3 = nn.Conv2d(num_feat + 2 * num_grow_ch, num_grow_ch, 3, 1, 1)
        self.conv4 = nn.Conv2d(num_feat + 3 * num_grow_ch, num_grow_ch, 3, 1, 1)
        self.conv5 = nn.Conv2d(num_feat + 4 * num_grow_ch, num_feat, 3, 1, 1)

        self.lrelu = nn.LeakyReLU(negative_slope=0.2, inplace=True)

        # 初期化
        self._initialize_weights()

    def _initialize_weights(self):
        for m in self.modules():
            if isinstance(m, nn.Conv2d):
                nn.init.kaiming_normal_(m.weight, a=0, mode='fan_in', nonlinearity='leaky_relu')
                if m.bias is not None:
                    nn.init.constant_(m.bias, 0)

    def forward(self, x):
        x1 = self.lrelu(self.conv1(x))
        x2 = self.lrelu(self.conv2(torch.cat((x, x1), 1)))
        x3 = self.lrelu(self.conv3(torch.cat((x, x1, x2), 1)))
        x4 = self.lrelu(self.conv4(torch.cat((x, x1, x2, x3), 1)))
        x5 = self.conv5(torch.cat((x, x1, x2, x3, x4), 1))
        return x5 * 0.2 + x


class RRDB(nn.Module):
    """Residual in Residual Dense Block."""

    def __init__(self, num_feat, num_grow_ch=32):
        super(RRDB, self).__init__()
        self.rdb1 = ResidualDenseBlock(num_feat, num_grow_ch)
        self.rdb2 = ResidualDenseBlock(num_feat, num_grow_ch)
        self.rdb3 = ResidualDenseBlock(num_feat, num_grow_ch)

    def forward(self, x):
        out = self.rdb1(x)
        out = self.rdb2(out)
        out = self.rdb3(out)
        return out * 0.2 + x


class RRDBNet(nn.Module):
    """Networks consisting of Residual in Residual Dense Block.

    Args:
        num_in_ch (int): Channel number of inputs.
        num_out_ch (int): Channel number of outputs.
        num_feat (int): Channel number of intermediate features.
        num_block (int): Block number in the trunk network.
        num_grow_ch (int): Channels for each growth.
        scale (int): Upscale factor.
    """

    def __init__(self, num_in_ch=3, num_out_ch=3, num_feat=64, num_block=23, num_grow_ch=32, scale=4):
        super(RRDBNet, self).__init__()
        self.scale = scale
        if scale == 2:
            num_in_ch = num_in_ch * 4
        elif scale == 1:
            num_in_ch = num_in_ch * 16
        
        self.conv_first = nn.Conv2d(num_in_ch, num_feat, 3, 1, 1)
        self.body = self._make_layer(RRDB, num_feat, num_block, num_grow_ch)
        self.conv_body = nn.Conv2d(num_feat, num_feat, 3, 1, 1)
        
        # upsample
        self.upconv1 = nn.Conv2d(num_feat, num_feat, 3, 1, 1)
        if self.scale >= 4:
            self.upconv2 = nn.Conv2d(num_feat, num_feat, 3, 1, 1)
        if self.scale >= 8:
            self.upconv3 = nn.Conv2d(num_feat, num_feat, 3, 1, 1)
        
        self.conv_hr = nn.Conv2d(num_feat, num_feat, 3, 1, 1)
        self.conv_last = nn.Conv2d(num_feat, num_out_ch, 3, 1, 1)

        self.lrelu = nn.LeakyReLU(negative_slope=0.2, inplace=True)
        
        # 初期化
        self._initialize_weights()
        
    def _make_layer(self, block, num_feat, num_blocks, num_grow_ch):
        layers = []
        for _ in range(num_blocks):
            layers.append(block(num_feat, num_grow_ch))
        return nn.Sequential(*layers)

    def _initialize_weights(self):
        for m in self.modules():
            if isinstance(m, nn.Conv2d):
                nn.init.kaiming_normal_(m.weight, a=0, mode='fan_in', nonlinearity='leaky_relu')
                if m.bias is not None:
                    nn.init.constant_(m.bias, 0)

    def forward(self, x):
        if self.scale == 2:
            feat = F.pixel_unshuffle(x, 2)
        elif self.scale == 1:
            feat = F.pixel_unshuffle(x, 4)
        else:
            feat = x
        
        feat = self.conv_first(feat)
        body_feat = self.body(feat)
        body_feat = self.conv_body(body_feat)
        feat = feat + body_feat
        
        # upsample
        feat = self.lrelu(self.upconv1(F.interpolate(feat, scale_factor=2, mode='nearest')))
        if self.scale >= 4:
            feat = self.lrelu(self.upconv2(F.interpolate(feat, scale_factor=2, mode='nearest')))
        if self.scale >= 8:
            feat = self.lrelu(self.upconv3(F.interpolate(feat, scale_factor=2, mode='nearest')))
        
        out = self.conv_last(self.lrelu(self.conv_hr(feat)))
        return out
