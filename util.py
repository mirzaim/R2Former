
import re
import torch
import shutil
import logging
# import torchscan
import numpy as np
from os.path import join
from sklearn.decomposition import PCA

import datasets_ws


# def get_flops(model, input_shape=(480, 640)):
#     """Return the FLOPs as a string, such as '22.33 GFLOPs'"""
#     assert len(input_shape) == 2, f"input_shape should have len==2, but it's {input_shape}"
#     module_info = torchscan.crawl_module(model, (3, input_shape[0], input_shape[1]))
#     output = torchscan.utils.format_info(module_info)
#     return re.findall("Floating Point Operations on forward: (.*)\n", output)[0]


def save_checkpoint(args, state, is_best, filename):
    model_path = join(args.save_dir, filename)
    torch.save(state, model_path)
    if is_best:
        shutil.copyfile(model_path, join(args.save_dir, "best_model.pth"))


def resume_train(args, model, optimizer=None, strict=False):
    """Load model, optimizer, and other training parameters"""
    logging.debug(f"Loading checkpoint: {args.resume}")
    checkpoint = torch.load(args.resume, map_location=('cpu' if args.device=='cpu' else None)) # , map_location='cpu'
    if "epoch_num" in checkpoint:
        start_epoch_num = checkpoint["epoch_num"]
    # del(checkpoint["model_state_dict"]['module.reranker.decoder_p
    # os_embed'])

    # print('module.backbone.cls_token' not in checkpoint)
    if args.backbone.startswith('deit') and 'module.backbone.cls_token' not in checkpoint["model_state_dict"]:
        for key in list(checkpoint["model_state_dict"].keys()):
            checkpoint["model_state_dict"][key.replace('module','module.backbone')] = checkpoint["model_state_dict"][key]
            del(checkpoint["model_state_dict"][key])
        # model.load_state_dict(checkpoint["model_state_dict"], strict=True)
        # raise Exception
    model.load_state_dict(checkpoint["model_state_dict"], strict=strict)
    if optimizer:
        optimizer.load_state_dict(checkpoint["optimizer_state_dict"])
    if "best_r5" in checkpoint:
        best_r5 = checkpoint["best_r5"]
        logging.debug(f"Loaded checkpoint: start_epoch_num = {start_epoch_num}, " \
                      f"current_best_R@5 = {best_r5:.1f}")
    else:
        best_r5 = 0
    not_improved_num = checkpoint["not_improved_num"]

    if args.resume.endswith("last_model.pth"):  # Copy best model to current save_dir
        shutil.copy(args.resume.replace("last_model.pth", "best_model.pth"), args.save_dir)
    return model, optimizer, best_r5, start_epoch_num, not_improved_num


def compute_pca(args, model, pca_dataset_folder, full_features_dim):
    model = model.eval()
    pca_ds = datasets_ws.PCADataset(args, args.datasets_folder, pca_dataset_folder)
    dl = torch.utils.data.DataLoader(pca_ds, args.infer_batch_size, shuffle=True)
    pca_features = np.empty([min(len(pca_ds), 2**14), full_features_dim])
    with torch.no_grad():
        for i, images in enumerate(dl):
            if i*args.infer_batch_size >= len(pca_features): break
            features = model(images).cpu().numpy()
            pca_features[i*args.infer_batch_size : (i*args.infer_batch_size)+len(features)] = features
    pca = PCA(args.pca_dim)
    pca.fit(pca_features)
    return pca

