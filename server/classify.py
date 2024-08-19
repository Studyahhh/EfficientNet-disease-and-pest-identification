import torch
from PIL import Image
from torchvision.transforms import transforms


def predict_top3_classes(model_path, class_names_path, image_path):
    # 设置设备
    device = "cuda" if torch.cuda.is_available() else "cpu"

    # 加载整个模型对象
    model = torch.load(model_path)

    # 确保模型在评估模式
    model = model.to(device)
    model.eval()

    # 定义数据预处理步骤
    data_transforms = transforms.Compose([
        transforms.Resize((224, 224)),
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])
    ])

    # 从txt文件读取类别名称和索引
    class_names = {}
    with open(class_names_path, "r", encoding='utf-8') as f:
        for line in f:
            idx, class_name = line.strip().split(": ")
            class_names[int(idx)] = class_name

    # 加载和预处理图像
    def process_image(image_path):
        image = Image.open(image_path).convert('RGB')
        image = data_transforms(image)
        image = image.unsqueeze(0)  # 增加批次维度
        return image.to(device)

    # 处理输入图像
    image = process_image(image_path)

    # 进行推断
    with torch.no_grad():
        outputs = model(image)
        probabilities = torch.nn.functional.softmax(outputs, dim=1)
        top3_prob, top3_catid = torch.topk(probabilities, 3)

    # 打印前三个概率最大的结果及其类别
    results = []
    for i in range(top3_prob.size(1)):
        class_id = top3_catid[0][i].item()
        prob_percentage = top3_prob[0][i].item()
        if prob_percentage < 0:
            continue
        else:
            prob_percentage_str = f"{prob_percentage:.2f}"
            # print('prob_percentage_str', prob_percentage_str)
            results.append((class_names[class_id], f"{prob_percentage_str}"))

    return results
